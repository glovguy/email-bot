import streamlit as st
from src.skills.persona import Persona

st.title("Personas")
st.divider()

# List all personas
personas = Persona.query.all()
for persona in personas:
    with st.expander(f"**{persona.name}**"):
        st.write(persona.description)
        st.write(f"System prompt: {persona.system_prompt}")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Delete", key=f"delete_{persona.id}"):
                Persona.query.filter_by(id=persona.id).delete()
                st.rerun()
        
        with col2:
            if st.button("Edit", key=f"edit_{persona.id}"):
                st.session_state.editing_persona = persona
                st.rerun()

# Add/Edit persona form
st.divider()
if 'editing_persona' in st.session_state:
    st.subheader("Edit Persona")
    persona = st.session_state.editing_persona
    name = st.text_input("Name", value=persona.name)
    description = st.text_area("Description", value=persona.description)
    system_prompt = st.text_area("System Prompt", value=persona.system_prompt)
    
    if st.button("Save Changes"):
        persona.name = name
        persona.description = description
        persona.system_prompt = system_prompt
        st.session_state.pop('editing_persona')
        st.rerun()
else:
    st.subheader("Add New Persona")
    
    # Initialize session state for form if not present
    if 'form_submitted' not in st.session_state:
        st.session_state.form_submitted = False
        
    name = st.text_input("Name", key="new_name", value="")
    description = st.text_area("Description", key="new_description", value="") 
    system_prompt = st.text_area("System Prompt", key="new_system_prompt", value="")
    
    if st.button("Add Persona"):
        try:
            new_persona = Persona(name=name, description=description, system_prompt=system_prompt)
            Persona.query.session.add(new_persona)
            Persona.query.session.commit()
            st.success("Successfully added new persona!")
            st.session_state.form_submitted = True
            st.rerun()
        except Exception as e:
            st.error(f"Error adding persona: {str(e)}")
