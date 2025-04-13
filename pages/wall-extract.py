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
                            linestyle = '-'
                            linewidth = 2.0
                            alpha = 0.9
                        else:  # Slab
                            linestyle = ':'
                            linewidth = 1.0
                            alpha = 0.7
                        
                        # Plot the element outline
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
                
                # Display simplified wall data - removed raw plotting data section
                st.write("### Raw Wall Data")
                if st.checkbox("Show simplified wall data"):
                    wall_data = []
                    for element in level_elements:
                        if element['type'] == 'Wall':
                            vertices = element['vertices']
                            
                            # Calculate wall centerline
                            # Group vertices into two main clusters (opposite faces of wall)
                            center = np.mean(vertices, axis=0)
                            # Project points onto principal direction using PCA
                            centered_pts = vertices - center
                            cov_matrix = np.cov(centered_pts.T)
                            eigenvalues, eigenvectors = np.linalg.eigh(cov_matrix)
                            # Principal direction is eigenvector with largest eigenvalue
                            principal_direction = eigenvectors[:, -1]
                            
                            # Project points onto principal direction
                            projected = np.dot(centered_pts, principal_direction)
                            
                            # Get the extreme points along the principal direction
                            min_idx = np.argmin(projected)
                            max_idx = np.argmax(projected)
                            
                            # Calculate centerline points
                            points_cluster1 = vertices[projected < np.mean(projected)]
                            points_cluster2 = vertices[projected >= np.mean(projected)]
                            
                            start_point = np.mean(points_cluster1, axis=0)
                            end_point = np.mean(points_cluster2, axis=0)
                            
                            # Calculate length
                            length = np.linalg.norm(end_point - start_point)
                            
                            wall_data.append({
                                'Name': element['name'],
                                'Elevation': round(element['elevation'], 2),
                                'Start_X': round(float(start_point[0]), 2),
                                'Start_Y': round(float(start_point[1]), 2),
                                'End_X': round(float(end_point[0]), 2),
                                'End_Y': round(float(end_point[1]), 2),
                                'Length': round(float(length), 2)
                            })
                    
                    if wall_data:
                        # Add format selection
                        data_format = st.radio(
                            "Select data format:",
                            ["Table", "JSON", "CSV", "XAML"],
                            horizontal=True
                        )
                        
                        st.write("### Simplified wall representation (start and end points):")
                        df = pd.DataFrame(wall_data)
                        
                        if data_format == "Table":
                            st.dataframe(df)
                        elif data_format == "JSON":
                            st.download_button(
                                "Download JSON",
                                df.to_json(orient='records'),
                                "wall_data.json",
                                "application/json",
                                key='download-json'
                            )
                            st.json(df.to_dict('records'))
                        elif data_format == "XAML":
                            # Convert data to XAML format
                            xaml_data = '<ResourceDictionary\n    xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"\n    xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml">\n'
                            xaml_data += '    <CompositeCollection x:Key="WallData">\n'
                            
                            for wall in wall_data:
                                xaml_data += f'        <Wall Name="{wall["Name"]}" Elevation="{wall["Elevation"]}">\n'
                                xaml_data += f'            <Point Start="{wall["Start_X"]},{wall["Start_Y"]}" End="{wall["End_X"]},{wall["End_Y"]}" />\n'
                                xaml_data += f'            <Length Value="{wall["Length"]}" />\n'
                                xaml_data += '        </Wall>\n'
                            
                            xaml_data += '    </CompositeCollection>\n'
                            xaml_data += '</ResourceDictionary>'
                            
                            st.download_button(
                                "Download XAML",
                                xaml_data,
                                "wall_data.xaml",
                                "application/xaml+xml",
                                key='download-xaml'
                            )
                            st.code(xaml_data, language='xml')
                        else:  # CSV
                            st.download_button(
                                "Download CSV",
                                df.to_csv(index=False),
                                "wall_data.csv",
                                "text/csv",
                                key='download-csv'
                            )
                            st.dataframe(df)

                        # Create new plot for simplified walls
                        st.write("### Simplified Wall Plot")
                        fig_simple, ax_simple = plt.subplots(figsize=(10, 10))
                        
                        # Plot each level with different colors
                        colors = plt.cm.tab10(np.linspace(0, 1, len(selected_storeys)))
                        for storey_name, color in zip(selected_storeys, colors):
                            # Filter walls for this storey
                            level_walls = [w for w in wall_data if w['Elevation'] == storey_data[storey_name]['elevation']]
                            
                            for wall in level_walls:
                                # Plot wall as a single line
                                ax_simple.plot([wall['Start_X'], wall['End_X']], 
                                             [wall['Start_Y'], wall['End_Y']],
                                             '-', linewidth=2.0,
                                             color=color,
                                             label=f"{storey_name}")
                        
                        # Remove duplicate labels
                        handles, labels = plt.gca().get_legend_handles_labels()
                        by_label = dict(zip(labels, handles))
                        plt.legend(by_label.values(), by_label.keys(),
                                 bbox_to_anchor=(1.05, 1.0),
                                 loc='upper left')
                        
                        ax_simple.set_aspect('equal')
                        ax_simple.grid(True)
                        plt.tight_layout()
                        fig_simple.set_size_inches(15, 10)
                        ax_simple.set_title("Simplified Wall Layout - Multiple Levels Overlay")
                        
                        # Display the simplified plot
                        st.pyplot(fig_simple)
                    else:
                        st.warning("No wall data available at selected levels")
                
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