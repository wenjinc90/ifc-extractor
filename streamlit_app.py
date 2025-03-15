import streamlit as st
import ifcopenshell
import tempfile
import os

st.set_page_config(layout="wide")  # Makes the app use full screen width

st.markdown("""
    <style>
        .stDataFrame {
            font-size: 12px;
        }
        .stDataFrame [data-testid="stHorizontalScrollbarContent"] {
            min-height: 450px;
        }
    </style>
    """, unsafe_allow_html=True)

st.title("IFC Model Extractor")
st.write("Upload your IFC file or select a sample file to extract model elements")

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
            # Sample file - direct path
            ifc_file = ifcopenshell.open(file_to_process)
        else:
            # Uploaded file - needs temporary handling
            with tempfile.NamedTemporaryFile(delete=False, suffix='.ifc') as tmp_file:
                tmp_file.write(file_to_process.getvalue())
                tmp_file_path = tmp_file.name
            ifc_file = ifcopenshell.open(tmp_file_path)
        
        # Get all element types in the model
        element_types = set(element.is_a() for element in ifc_file)
        
        # Define default element types to pre-select
        default_types = [
            'IfcWall', 'IfcWallStandardCase', 'IfcSlab', 
            'IfcColumn', 'IfcBeam', 'IfcMember'
        ]
        
        # Filter default types to only include those present in the model
        default_selected = [t for t in default_types if t in element_types]
        
        # Create a multiselect for element types with defaults
        selected_types = st.multiselect(
            "Select element types to extract:",
            options=sorted(list(element_types)),
            default=default_selected
        )
        
        if selected_types:
            for element_type in selected_types:
                elements = ifc_file.by_type(element_type)
                st.write(f"### {element_type} ({len(elements)} elements)")
                
                # Display element information in a table
                element_data = []
                for element in elements:
                    try:
                        # Basic properties
                        data = {
                            "Name": element.Name if hasattr(element, "Name") else "Unnamed",
                            "GUID": element.GlobalId
                        }
                        
                        # Get location
                        if hasattr(element, "ObjectPlacement"):
                            placement = element.ObjectPlacement
                            if hasattr(placement, "RelativePlacement"):
                                location = placement.RelativePlacement.Location
                                if location:
                                    data.update({
                                        "X": round(location.Coordinates[0], 2),
                                        "Y": round(location.Coordinates[1], 2),
                                        "Z": round(location.Coordinates[2], 2)
                                    })
                        
                        # Get dimensions
                        if hasattr(element, "Representation"):
                            rep = element.Representation
                            if rep:
                                # Get quantities from property sets
                                for definition in element.IsDefinedBy:
                                    if definition.is_a("IfcRelDefinesByProperties"):
                                        property_set = definition.RelatingPropertyDefinition
                                        if property_set.is_a("IfcElementQuantity"):
                                            for quantity in property_set.Quantities:
                                                if quantity.is_a("IfcQuantityLength"):
                                                    data[quantity.Name] = round(quantity.LengthValue, 2)
                                                elif quantity.is_a("IfcQuantityArea"):
                                                    data[quantity.Name] = round(quantity.AreaValue, 2)
                                                elif quantity.is_a("IfcQuantityVolume"):
                                                    data[quantity.Name] = round(quantity.VolumeValue, 2)
                        
                        element_data.append(data)
                    except Exception as e:
                        st.error(f"Error processing element: {e}")
                
                if element_data:
                    st.dataframe(
                        element_data,
                        use_container_width=True,
                        hide_index=True,
                        height=400  # Adjust this value based on your needs
                    )
        
    except Exception as e:
        st.error(f"Error processing IFC file: {e}")
    finally:
        # Clean up temporary file only for uploads
        if isinstance(file_to_process, str) == False and 'tmp_file_path' in locals():
            os.unlink(tmp_file_path)
else:
    st.info("Please select or upload an IFC file to begin")
