import streamlit as st
import ifcopenshell
import ifcopenshell.geom
import tempfile
import os
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd

st.set_page_config(layout="wide")

st.title("IFC Slab Plan Extractor")
st.write("Upload your IFC file or select a sample file to extract and view floor plans")

# Add radio button for selection
input_method = st.radio(
    "Choose input method:",
    ("Upload your own IFC file", "Use sample IFC file")
)

if input_method == "Upload your own IFC file":
    uploaded_file = st.file_uploader("Choose an IFC file", type=['ifc'])
    file_to_process = uploaded_file
else:
    # List sample files from the samples directory
    sample_files = [f for f in os.listdir("samples") if f.endswith('.ifc')]
    if sample_files:
        selected_sample = st.selectbox(
            "Select a sample IFC file",
            sample_files
        )
        file_to_process = os.path.join("samples", selected_sample)
    else:
        st.error("No sample IFC files found in samples directory")
        file_to_process = None

if file_to_process is not None:
    try:
        # Handle both uploaded and sample files
        if isinstance(file_to_process, str):
            ifc_file = ifcopenshell.open(file_to_process)
        else:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.ifc') as tmp_file:
                tmp_file.write(file_to_process.getvalue())
                tmp_file_path = tmp_file.name
            ifc_file = ifcopenshell.open(tmp_file_path)

        # First get all building storeys from the model
        storeys = ifc_file.by_type('IfcBuildingStorey')
        if not storeys:
            st.warning("No building storeys found in the model")
            st.stop()  # Use st.stop() instead of return in Streamlit
            
        # Create a dictionary to store storey data
        storey_data = {}
        
        # Process each storey
        for storey in storeys:
            # Get elements related to this storey
            rel_elements = []
            if hasattr(storey, 'ContainsElements'):
                for rel in storey.ContainsElements:
                    rel_elements.extend(rel.RelatedElements)
            
            # Filter slabs and walls
            storey_slabs = [e for e in rel_elements if e.is_a('IfcSlab')]
            storey_walls = [e for e in rel_elements if e.is_a('IfcWall') or e.is_a('IfcWallStandardCase')]
            
            if storey_slabs or storey_walls:
                element_data = []
                
                # Process slabs in this storey
                for slab in storey_slabs:
                    try:
                        settings = ifcopenshell.geom.settings()
                        settings.set(settings.USE_WORLD_COORDS, True)
                        shape = ifcopenshell.geom.create_shape(settings, slab)
                        verts = shape.geometry.verts
                        faces = shape.geometry.faces
                        
                        vertices = np.array(verts).reshape((-1, 3))
                        vertices_2d = vertices[:, [0, 1]]
                        
                        element_info = {
                            'type': 'Slab',
                            'name': slab.Name if hasattr(slab, 'Name') else "Unnamed",
                            'vertices': vertices_2d,
                            'faces': np.array(faces).reshape((-1, 3)),
                            'elevation': float(storey.Elevation)
                        }
                        element_data.append(element_info)
                    except Exception as e:
                        st.warning(f"Could not process slab {slab.GlobalId}: {str(e)}")
                
                # Process walls in this storey
                for wall in storey_walls:
                    try:
                        settings = ifcopenshell.geom.settings()
                        settings.set(settings.USE_WORLD_COORDS, True)
                        shape = ifcopenshell.geom.create_shape(settings, wall)
                        verts = shape.geometry.verts
                        faces = shape.geometry.faces
                        
                        vertices = np.array(verts).reshape((-1, 3))
                        vertices_2d = vertices[:, [0, 1]]
                        
                        element_info = {
                            'type': 'Wall',
                            'name': wall.Name if hasattr(wall, 'Name') else "Unnamed",
                            'vertices': vertices_2d,
                            'faces': np.array(faces).reshape((-1, 3)),
                            'elevation': float(storey.Elevation)
                        }
                        element_data.append(element_info)
                    except Exception as e:
                        st.warning(f"Could not process wall {wall.GlobalId}: {str(e)}")
                
                if element_data:
                    storey_data[storey.Name] = {
                        'elevation': float(storey.Elevation),
                        'elements': element_data
                    }
                    
        if storey_data:
            st.write(f"Found {len(storey_data)} storeys with elements")
            
            # Let user select storeys
            selected_storeys = st.multiselect(
                "Select floor levels:",
                list(storey_data.keys()),
                default=[list(storey_data.keys())[0]] if storey_data else []
            )

            # For each selected storey, let user choose element types
            level_elements = []
            for storey_name in selected_storeys:
                st.write(f"### {storey_name}")
                storey = storey_data[storey_name]
                
                # Get available element types in this storey
                available_types = set(e['type'] for e in storey['elements'])
                
                # Let user select element types for this storey
                selected_types = st.multiselect(
                    f"Select element types for {storey_name}:",
                    list(available_types),
                    default=list(available_types)
                )
                
                # Add selected elements to the list
                level_elements.extend([
                    e for e in storey['elements']
                    if e['type'] in selected_types
                ])
            
            # Continue with existing visualization code using filtered level_elements
            if level_elements:
                # Create the plot
                fig, ax = plt.subplots(figsize=(10, 10))
                
                # Plot each storey with different colors
                colors = plt.cm.tab10(np.linspace(0, 1, len(selected_storeys)))
                for storey_name, color in zip(selected_storeys, colors):
                    storey = storey_data[storey_name]
                    storey_elements = [e for e in level_elements 
                                     if abs(e['elevation'] - storey['elevation']) < 0.1]
                    
                    for element in storey_elements:
                        vertices = element['vertices']
                        faces = element['faces']
                        
                        # Different styles for walls and slabs
                        if element['type'] == 'Wall':
                            edge_linestyle = '-'
                            edge_linewidth = 0.3  # Made thinner
                            edge_alpha = 1.0
                            fill_color = 'lightgrey'
                            fill_alpha = 0.3
                            
                            # First fill the triangulated surfaces
                            for face in faces:
                                face_vertices = vertices[face]
                                ax.fill(face_vertices[:, 0], face_vertices[:, 1],
                                      color=fill_color,
                                      alpha=fill_alpha)
                            
                            # Then plot the edges
                            edges = set()
                            for face in faces:
                                for i in range(len(face)):
                                    edge = tuple(sorted([face[i], face[(i+1)%len(face)]]))
                                    edges.add(edge)
                            
                            for edge in edges:
                                edge_vertices = vertices[list(edge)]
                                ax.plot(edge_vertices[:, 0], edge_vertices[:, 1],
                                      linestyle=edge_linestyle,
                                      linewidth=edge_linewidth,
                                      color=color,
                                      alpha=edge_alpha,
                                      label=f"{storey_name} - {element['type']}")
                        else:  # Slab
                            linestyle = ':'
                            linewidth = 0.5  # Reduced from 1.0
                            alpha = 0.7
                            
                            # Plot the element outline for slabs
                            for face in faces:
                                face_vertices = vertices[face]
                                face_vertices = np.vstack((face_vertices, face_vertices[0]))
                                ax.plot(face_vertices[:, 0], face_vertices[:, 1],
                                      linestyle=linestyle,
                                      linewidth=linewidth,
                                      color=color,
                                      alpha=alpha,
                                      label=f"{storey_name} - {element['type']}")
                
                # Remove duplicate labels
                handles, labels = plt.gca().get_legend_handles_labels()
                by_label = dict(zip(labels, handles))
                # Move legend outside the plot to the right
                plt.legend(by_label.values(), by_label.keys(), 
                         bbox_to_anchor=(1.05, 1.0),
                         loc='upper left')
                
                ax.set_aspect('equal')
                ax.grid(True)
                # Customize grid with moderate visibility
                ax.grid(True, which='major', linestyle='-', linewidth=0.6, alpha=0.4)  # Reduced thickness and opacity
                ax.grid(True, which='minor', linestyle=':', linewidth=0.3, alpha=0.3)  # Reduced thickness and opacity
                ax.minorticks_on()  # Enable minor ticks
                # Set grid intervals
                ax.xaxis.set_major_locator(plt.MultipleLocator(1.0))  # Major grid every 1 unit
                ax.xaxis.set_minor_locator(plt.MultipleLocator(0.1))  # Minor grid every 0.1 units
                ax.yaxis.set_major_locator(plt.MultipleLocator(1.0))
                ax.yaxis.set_minor_locator(plt.MultipleLocator(0.1))
                
                # Add grid color with lighter shades
                ax.set_axisbelow(True)  # Put grid below other elements
                ax.grid(which='major', color='#888888')  # Lighter color for major grid
                ax.grid(which='minor', color='#AAAAAA')  # Lighter color for minor grid
                
                # Adjust the layout to prevent legend cutoff
                plt.tight_layout()
                # Adjust figure size to accommodate legend
                fig.set_size_inches(15, 10)  # Width increased to accommodate legend
                ax.set_title("Floor Plans - Multiple Levels Overlay")
                
                # Display the plot in Streamlit
                st.pyplot(fig)
                
                # Display element information in a table
                element_info = [{
                    'Type': element['type'],
                    'Name': element['name'],
                    'Elevation': round(element['elevation'], 2),
                    'Vertex Count': len(element['vertices']),
                    'Face Count': len(element['faces'])
                } for element in level_elements]
                
                st.write("### Element Information")
                st.dataframe(element_info)

            else:
                st.warning("Please select at least one level to view")
        else:
            st.warning("No valid element geometry could be extracted")
            
    except Exception as e:
        st.error(f"Error processing IFC file: {e}")
    finally:
        if isinstance(file_to_process, str) == False and 'tmp_file_path' in locals():
            os.unlink(tmp_file_path)
else:
    st.info("Please select or upload an IFC file to begin")