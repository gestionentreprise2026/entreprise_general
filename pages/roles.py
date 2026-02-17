from utils import apply_base_ui
apply_base_ui()

from auth import require_login, sidebar_session, require_roles

require_login()
sidebar_session()
require_roles("ADMIN", "ASISTENTE", "SOCIO")

st.title("🛡️ Roles")
st.info("Aquí administraremos roles/permisos.")
