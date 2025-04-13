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

        # Get all slabs and walls from the model
        slabs = ifc_file.by_type('IfcSlab')
        walls = ifc_file.by_type('IfcWall') + ifc_file.by_type('IfcWallStandardCase')
        
        if slabs or walls:
            st.write(f"Found {len(slabs)} slabs and {len(walls)} walls in the model")
            
            # Create settings for geometry computation
            settings = ifcopenshell.geom.settings()
            
            # Store element data for plotting
            element_data = []
            
            # Process slabs
            for slab in slabs:
                try:
                    # Get geometry with global coordinates
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
                        'elevation': np.mean(vertices[:, 2])
                    }
                    element_data.append(element_info)
                except Exception as e:
                    st.warning(f"Could not process slab {slab.GlobalId}: {str(e)}")
            
            # Process walls
            for wall in walls:
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
                        'elevation': np.mean(vertices[:, 2])
                    }
                    element_data.append(element_info)
                except Exception as e:
                    st.warning(f"Could not process wall {wall.GlobalId}: {str(e)}")
            
            if element_data:
                # Sort elements by elevation
                element_data.sort(key=lambda x: x['elevation'])
                unique_elevations = sorted(set(round(s['elevation'], 2) for s in element_data))
                
                # Let user select multiple levels to view
                selected_elevations = st.multiselect(
                    "Select floor levels to view:",
                    unique_elevations,
                    default=[unique_elevations[0]],
                    format_func=lambda x: f"Level at {x*1000:.0f}mm from reference" if x < 0 else f"Level at elevation {x:.2f}m"
                )
                
                # Filter elements for selected elevations
                level_elements = [e for e in element_data if round(e['elevation'], 2) in selected_elevations]
                
                if level_elements:
                    # Create the plot
                    fig, ax = plt.subplots(figsize=(10, 10))
                    
                    # Plot each level with different colors
                    colors = plt.cm.tab10(np.linspace(0, 1, len(selected_elevations)))
                    for elevation, color in zip(selected_elevations, colors):
                        elevation_elements = [e for e in level_elements if round(e['elevation'], 2) == elevation]
                        
                        for element in elevation_elements:
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
                                      label=f"Level {elevation:.2f}m - {element['type']}")
                    
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
                    
                else:
                    st.warning("Please select at least one level to view")
            else:
                st.warning("No valid element geometry could be extracted")
        else:
            st.warning("No slabs or walls found in the model")
            
    except Exception as e:
        st.error(f"Error processing IFC file: {e}")
    finally:
        if isinstance(file_to_process, str) == False and 'tmp_file_path' in locals():
            os.unlink(tmp_file_path)
else:
    st.info("Please select or upload an IFC file to begin")