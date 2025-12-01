import streamlit as st
from inference import process_id
from PIL import Image
import tempfile
import json
import difflib

st.set_page_config(page_title="Aadhaar KYC Checker", layout="centered")

st.title("🔍 Aadhaar KYC – Extract & Match")
st.write("Upload your Aadhaar card image and enter your details. "
         "We'll compare your inputs with the information extracted from the document.")

# ---------- User inputs ----------
st.subheader("🧑 User-entered details")

user_name = st.text_input("Full Name (as entered in form)")
user_aadhaar = st.text_input("Aadhaar Number (as entered in form)", help="You can enter with or without spaces")
user_dob = st.text_input("Date of Birth (DD/MM/YYYY)", help="Use same format as Aadhaar")

# ---------- File uploader ----------
st.subheader("🪪 Upload Aadhaar image")

uploaded_file = st.file_uploader(
    "Upload Aadhaar front image",
    type=["jpg", "jpeg", "png"],
    help="Supported formats: JPG, JPEG, PNG"
)

save_json_flag = st.checkbox("Save JSON via process_id", value=False)
output_json_name = st.text_input("Output JSON filename", value="aadhaar_output.json")
verbose_flag = st.checkbox("Verbose logging", value=False)


def char_similarity(a: str, b: str) -> float:
    """
    Character-level similarity using SequenceMatcher.
    Returns a score between 0 and 100.
    """
    if not a and not b:
        return 100.0
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio() * 100.0


def jaccard_token_similarity(a: str, b: str) -> float:
    """
    Token-level Jaccard similarity (for names, addresses, etc.).
    Returns a score between 0 and 100.
    """
    tokens_a = set(a.split())
    tokens_b = set(b.split())
    if not tokens_a and not tokens_b:
        return 100.0
    if not tokens_a or not tokens_b:
        return 0.0
    inter = tokens_a.intersection(tokens_b)
    union = tokens_a.union(tokens_b)
    return (len(inter) / len(union)) * 100.0


def name_match_score(user_name_norm: str, doc_name_norm: str) -> float:
    """
    Combined name similarity: 60% character-level + 40% token-level.
    """
    char_sim = char_similarity(user_name_norm, doc_name_norm)
    token_sim = jaccard_token_similarity(user_name_norm, doc_name_norm)
    return 0.6 * char_sim + 0.4 * token_sim


def diff_html(user_str: str, doc_str: str, label_user="User", label_doc="Doc") -> str:
    """
    Generate HTML highlighting differences between user_str and doc_str.
    Equal characters: normal
    Different/extra/missing: red background
    """
    s = difflib.SequenceMatcher(None, user_str, doc_str)
    user_out = []
    doc_out = []

    for tag, i1, i2, j1, j2 in s.get_opcodes():
        u_sub = user_str[i1:i2]
        d_sub = doc_str[j1:j2]

        if tag == "equal":
            user_out.append(f"<span>{u_sub}</span>")
            doc_out.append(f"<span>{d_sub}</span>")
        elif tag == "replace":
            user_out.append(f"<span style='background-color:#ffcccc;'>{u_sub}</span>")
            doc_out.append(f"<span style='background-color:#ffcccc;'>{d_sub}</span>")
        elif tag == "delete":
            user_out.append(f"<span style='background-color:#ffcccc;text-decoration:line-through;'>{u_sub}</span>")
        elif tag == "insert":
            doc_out.append(f"<span style='background-color:#ffcccc;'>{d_sub}</span>")

    html = f"""
    <div style="font-family:monospace; line-height:1.6;">
      <div><strong>{label_user}:</strong> {''.join(user_out)}</div>
      <div><strong>{label_doc} :</strong> {''.join(doc_out)}</div>
    </div>
    """
    return html


# ---------- Normalization helpers ----------
def normalize_name(name: str) -> str:
    if not name:
        return ""
    return " ".join(name.strip().lower().split())

def normalize_aadhaar(aadhaar: str) -> str:
    if not aadhaar:
        return ""
    return aadhaar.replace(" ", "").strip()

def normalize_dob(dob: str) -> str:
    if not dob:
        return ""
    return dob.strip()


# ---------- Main action ----------
if uploaded_file is not None:
    image = Image.open(uploaded_file)
    st.image(image, caption="Uploaded Aadhaar Image", use_column_width=True)

    if st.button("🚀 Extract & Compare"):
        
        
        
        # Save uploaded image to a temporary path
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
            tmp.write(uploaded_file.getbuffer())
            temp_image_path = tmp.name

        with st.spinner("Running YOLOv11 + OCR pipeline..."):
            result = process_id(
                image_path=temp_image_path,
                save_json=save_json_flag,
                output_json=output_json_name,
                verbose=verbose_flag
            )

        st.success("Extraction complete!")

        st.subheader("📄 Raw Extracted JSON")
        st.json(result)

        fields = result.get("fields", {})

        doc_name = fields.get("Name", "")
        doc_aadhaar = fields.get("Aadhaar", "")
        doc_dob = fields.get("DOB", "")

        # Normalized comparison
        user_name_norm = normalize_name(user_name)
        doc_name_norm = normalize_name(doc_name)

        user_aadhaar_norm = normalize_aadhaar(user_aadhaar)
        doc_aadhaar_norm = normalize_aadhaar(doc_aadhaar)

        user_dob_norm = normalize_dob(user_dob)
        doc_dob_norm = normalize_dob(doc_dob)
        
        # Fuzzy scores
        name_score = name_match_score(user_name_norm, doc_name_norm)  # 0–100
        aadhaar_score = char_similarity(user_aadhaar_norm, doc_aadhaar_norm)
        dob_score = char_similarity(user_dob_norm, doc_dob_norm)


        # name_match = user_name_norm != "" and (user_name_norm == doc_name_norm)
        # aadhaar_match = user_aadhaar_norm != "" and (user_aadhaar_norm == doc_aadhaar_norm)
        # dob_match = user_dob_norm != "" and (user_dob_norm == doc_dob_norm)
        
        NAME_THRESHOLD = 90.0
        AADHAAR_THRESHOLD = 98.0   # Aadhaar should be almost exact
        DOB_THRESHOLD = 95.0

        name_match = user_name_norm != "" and (name_score >= NAME_THRESHOLD)
        aadhaar_match = user_aadhaar_norm != "" and (aadhaar_score >= AADHAAR_THRESHOLD)
        dob_match = user_dob_norm != "" and (dob_score >= DOB_THRESHOLD)


        # st.subheader("✅ Matching result")

        # # Overall simple verdict
        # if name_match and aadhaar_match and dob_match:
        #     st.success("All three fields match between user input and Aadhaar document.")
        # else:
        #     st.warning("There are some mismatches between user input and Aadhaar document.")

        # # Detailed per-field table
        # st.write("### Field-wise comparison")

        # comparison_rows = [
        #     {
        #         "Field": "Name",
        #         "User Input": user_name,
        #         "From Document": doc_name,
        #         "Match": "✅ Match" if name_match else "❌ Mismatch"
        #     },
        #     {
        #         "Field": "Aadhaar Number",
        #         "User Input": user_aadhaar,
        #         "From Document": doc_aadhaar,
        #         "Match": "✅ Match" if aadhaar_match else "❌ Mismatch"
        #     },
        #     {
        #         "Field": "Date of Birth",
        #         "User Input": user_dob,
        #         "From Document": doc_dob,
        #         "Match": "✅ Match" if dob_match else "❌ Mismatch"
        #     }
        # ]

        # st.table(comparison_rows)
        st.subheader("✅ Matching result")

        # Overall verdict using fuzzy thresholds
        if name_match and aadhaar_match and dob_match:
            st.success("All three fields match (within fuzzy thresholds) between user input and Aadhaar document.")
        else:
            st.warning("Some fields have low match scores between user input and Aadhaar document.")

        st.write("### Field-wise comparison with fuzzy scores")

        # ---- NAME ----
        st.markdown("**Name**")
        st.write(f"Match score: `{name_score:.1f}%` (threshold: {NAME_THRESHOLD}%)")
        st.markdown(
            diff_html(user_name, doc_name, label_user="User Name", label_doc="Doc Name"),
            unsafe_allow_html=True
        )

        st.markdown("---")

        # ---- AADHAAR ----
        st.markdown("**Aadhaar Number**")
        st.write(f"Match score: `{aadhaar_score:.1f}%` (threshold: {AADHAAR_THRESHOLD}%)")
        st.markdown(
            diff_html(user_aadhaar, doc_aadhaar, label_user="User Aadhaar", label_doc="Doc Aadhaar"),
            unsafe_allow_html=True
        )

        st.markdown("---")

        # ---- DOB ----
        st.markdown("**Date of Birth**")
        st.write(f"Match score: `{dob_score:.1f}%` (threshold: {DOB_THRESHOLD}%)")
        st.markdown(
            diff_html(user_dob, doc_dob, label_user="User DOB", label_doc="Doc DOB"),
            unsafe_allow_html=True
        )

else:
    st.info("Please upload an Aadhaar image and fill in your details, then click 'Extract & Compare'.")


