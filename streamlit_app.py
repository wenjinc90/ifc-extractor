import streamlit as st
import ifcopenshell
import tempfile
import os

st.title("IFC Model Extractor")
st.write("Upload your IFC file to extract model elements")

uploaded_file = st.file_uploader("Choose an IFC file", type=['ifc'])

if uploaded_file is not None:
    # Save uploaded file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix='.ifc') as tmp_file:
        tmp_file.write(uploaded_file.getvalue())
        tmp_file_path = tmp_file.name

    try:
        # Load the IFC file
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
                    st.table(element_data)
        
    except Exception as e:
        st.error(f"Error processing IFC file: {e}")
    finally:
        # Clean up temporary file
        os.unlink(tmp_file_path)
else:
    st.info("Please upload an IFC file to begin")
