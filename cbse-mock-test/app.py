from __future__ import annotations

import html
import json
import os
import re
import time
import uuid
from datetime import datetime
from io import BytesIO
from pathlib import Path

import streamlit as st
from google import genai
from google.genai import types
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, HRFlowable

MODEL = "gemini-3.5-flash-lite"
SESSION = "2026-27"
CLASSES = ["Class XI", "Class XII"]
SUBJECTS = ["Mathematics", "Physics", "Chemistry", "Biology"]
TOTALS = {"Mathematics": 80, "Physics": 70, "Chemistry": 70, "Biology": 70}
TIME_LIMIT_SECONDS = 3 * 60 * 60

SYLLABUS = {
("Class XI","Mathematics"): "Sets|Relations and Functions|Trigonometric Functions|Complex Numbers and Quadratic Equations|Linear Inequalities|Permutations and Combinations|Binomial Theorem|Sequence and Series|Straight Lines|Conic Sections|Introduction to Three-dimensional Geometry|Limits and Derivatives|Statistics|Probability",
("Class XII","Mathematics"): "Relations and Functions|Inverse Trigonometric Functions|Matrices|Determinants|Continuity and Differentiability|Applications of Derivatives|Integrals|Applications of Integrals|Differential Equations|Vector Algebra|Three-dimensional Geometry|Linear Programming|Probability",
("Class XI","Physics"): "Units and Measurements|Motion in a Straight Line|Motion in a Plane|Laws of Motion|Work, Energy and Power|System of Particles and Rotational Motion|Gravitation|Mechanical Properties of Solids|Mechanical Properties of Fluids|Thermal Properties of Matter|Thermodynamics|Kinetic Theory|Oscillations|Waves",
("Class XII","Physics"): "Electric Charges and Fields|Electrostatic Potential and Capacitance|Current Electricity|Moving Charges and Magnetism|Magnetism and Matter|Electromagnetic Induction|Alternating Current|Electromagnetic Waves|Ray Optics and Optical Instruments|Wave Optics|Dual Nature of Radiation and Matter|Atoms|Nuclei|Semiconductor Electronics: Materials, Devices and Simple Circuits",
("Class XI","Chemistry"): "Some Basic Concepts of Chemistry|Structure of Atom|Classification of Elements and Periodicity in Properties|Chemical Bonding and Molecular Structure|Chemical Thermodynamics|Equilibrium|Redox Reactions|Organic Chemistry: Some Basic Principles and Techniques|Hydrocarbons",
("Class XII","Chemistry"): "Solutions|Electrochemistry|Chemical Kinetics|d- and f-Block Elements|Coordination Compounds|Haloalkanes and Haloarenes|Alcohols, Phenols and Ethers|Aldehydes, Ketones and Carboxylic Acids|Amines|Biomolecules",
("Class XI","Biology"): "The Living World|Biological Classification|Plant Kingdom|Animal Kingdom|Morphology of Flowering Plants|Anatomy of Flowering Plants|Structural Organisation in Animals|Cell: The Unit of Life|Biomolecules|Cell Cycle and Cell Division|Photosynthesis in Higher Plants|Respiration in Plants|Plant Growth and Development|Breathing and Exchange of Gases|Body Fluids and Circulation|Excretory Products and their Elimination|Locomotion and Movement|Neural Control and Coordination|Chemical Coordination and Integration",
("Class XII","Biology"): "Sexual Reproduction in Flowering Plants|Human Reproduction|Reproductive Health|Principles of Inheritance and Variation|Molecular Basis of Inheritance|Evolution|Human Health and Diseases|Microbes in Human Welfare|Biotechnology: Principles and Processes|Biotechnology and its Applications|Organisms and Populations|Ecosystem|Biodiversity and its Conservation",
}

BLUEPRINT_70 = [("A",16,1),("B",5,2),("C",7,3),("D",2,4),("E",3,5)]
BLUEPRINT_80 = [("A",20,1),("B",5,2),("C",6,3),("D",4,5),("E",3,4)]

st.set_page_config(page_title="CBSE Timed Mock Test", page_icon="📝", layout="wide")
st.markdown("""
<style>
.block-container{max-width:1000px;padding-top:1.5rem}
.hero{padding:1.4rem 1.6rem;border-radius:18px;background:linear-gradient(125deg,#092744,#086b86);color:white}
.hero h1{color:white;margin:0}.hero p{color:#d6f1fb;margin:.3rem 0 0}
.timer{font-size:1.45rem;font-weight:800;color:#063b68}
</style>
<div class="hero"><h1>CBSE Timed Mock Test</h1>
<p>Fresh full-syllabus papers for Classes XI and XII</p></div>
""", unsafe_allow_html=True)

try:
    API_KEY = str(st.secrets["GEMINI_API_KEY"])
except Exception:
    API_KEY = os.environ.get("GEMINI_API_KEY")
CLIENT = genai.Client(api_key=API_KEY) if API_KEY else None

def total_marks(subject):
    return TOTALS[subject]

def blueprint(subject):
    return BLUEPRINT_80 if subject == "Mathematics" else BLUEPRINT_70

def strip_json_fence(text):
    text = (text or "").strip()
    fence = chr(96) * 3
    if text.startswith(fence):
        text = re.sub(r"^" + re.escape(fence) + r"(?:json)?\s*", "", text)
        text = re.sub(r"\s*" + re.escape(fence) + r"$", "", text)
    return json.loads(text)

def create_prompt(class_name, subject, code):
    total = total_marks(subject)
    outline = "\n".join(
        f"Section {section}: {count} questions, {marks} mark(s) each."
        for section, count, marks in blueprint(subject)
    )
    if subject == "Mathematics":
        objective = "Section A: 18 MCQs and 2 assertion-reason questions, four options each."
        style = "CBSE Class XII-style structure: A 20x1, B 5x2, C 6x3, D 4x5, E 3 case-based x4."
    elif subject == "Chemistry":
        objective = "Section A: 16 MCQs, four options each."
        style = "CBSE science structure: A 16x1, B 5x2, C 7x3, D 2 case-based x4, E 3x5."
    else:
        objective = "Section A: 12 MCQs and 4 assertion-reason questions, four options each."
        style = "CBSE science structure: A 16x1, B 5x2, C 7x3, D 2 case-based x4, E 3x5."
    class_note = (
        "Use the current CBSE Class XII sample-paper question design."
        if class_name == "Class XII"
        else "Class XI exams are school-set; use a CBSE-style format aligned to the syllabus, and do not claim there is one nationwide Class XI paper format."
    )
    chapters = SYLLABUS[(class_name, subject)].split("|")
    return f"""
Create a fresh original, printable CBSE-style full-syllabus mock question paper.
Paper code: {code}
Academic session: {SESSION}
Class: {class_name}; Subject: {subject}; Maximum marks: {total}; Duration: 3 hours.
Use questions only from these syllabus chapters: {", ".join(chapters)}.
{outline}
{style}
{objective}
{class_note}

Write original questions; do not copy or closely paraphrase public sample papers.
Make all questions solvable from printed text, with any needed data included.
Balance difficulty: roughly 30 percent accessible, 50 percent standard, 20 percent challenging.
Numerical questions must have internally consistent values and solutions.
Written and case-based questions need marking points whose marks sum to the question maximum.
Some written questions may include an internal choice of equal marks. Do not add images.
Create exactly the question count and marks required by the blueprint; no extras.
Use ids A1, A2, B1, etc., in section order. Every objective question needs four options and a correct answer letter.
Return only valid JSON in this shape:
{{"questions":[{{"id":"A1","section":"A","marks":1,"kind":"mcq","prompt":"...","options":["A. ...","B. ...","C. ...","D. ..."],"correct_answer":"B","model_answer":"...","marking_points":[{{"point":"...","marks":1}}],"internal_choice":null}}]}}
Kinds: mcq, assertion_reason, written, case_based, long_answer.
Non-objective questions use empty options and empty correct_answer. An optional internal_choice must contain prompt, model_answer, and marking_points. The model answer is for private scoring only; exclude it from the printable paper.
"""

def make_paper(class_name, subject):
    if CLIENT is None:
        raise RuntimeError("Add GEMINI_API_KEY in Streamlit Secrets before creating a paper.")
    code = uuid.uuid4().hex[:8].upper()
    prompt = create_prompt(class_name, subject, code)
    last_error = None
    for _ in range(2):
        try:
            response = CLIENT.models.generate_content(
                model=MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.8,
                    max_output_tokens=24000,
                ),
            )
            questions = strip_json_fence(response.text).get("questions")
            if not isinstance(questions, list):
                raise ValueError("No questions returned.")
            expected_count = sum(row[1] for row in blueprint(subject))
            if len(questions) != expected_count:
                raise ValueError(f"Expected {expected_count} questions, got {len(questions)}.")
            if sum(int(q.get("marks", 0)) for q in questions) != total_marks(subject):
                raise ValueError("Generated question marks do not add up.")
            expected_sections = {row[0]: row[1] for row in blueprint(subject)}
            got_sections = {s: 0 for s in expected_sections}
            ids = set()
            for q in questions:
                q["id"] = str(q["id"])
                q["section"] = str(q["section"]).upper()
                if q["id"] in ids or q["section"] not in got_sections:
                    raise ValueError("Question ids or sections are invalid.")
                ids.add(q["id"])
                got_sections[q["section"]] += 1
                if not str(q.get("prompt", "")).strip():
                    raise ValueError(f"Question {q['id']} is blank.")
                q["marks"] = int(q["marks"])
                q["options"] = q.get("options") or []
                q["marking_points"] = q.get("marking_points") or []
                if q.get("kind") in ("mcq", "assertion_reason") and len(q["options"]) != 4:
                    raise ValueError(f"Question {q['id']} needs four choices.")
            if got_sections != expected_sections:
                raise ValueError("Generated section counts do not match.")
            return {
                "id": code, "class": class_name, "subject": subject,
                "total_marks": total_marks(subject), "created": datetime.now().strftime("%d %b %Y, %I:%M %p"),
                "questions": questions,
            }
        except Exception as error:
            last_error = error
            prompt += "\nRegenerate the complete JSON. Validation failed: " + str(error)
    raise RuntimeError(f"Could not generate a valid paper: {last_error}")

def register_font():
    font = Path(__import__("reportlab").__file__).parent / "fonts" / "Vera.ttf"
    if font.exists():
        if "Vera" not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont("Vera", str(font)))
        return "Vera"
    return "Helvetica"

def para_text(value):
    return html.escape(str(value)).replace("\n", "<br/>")

def make_pdf(paper):
    stream = BytesIO()
    font = register_font()
    doc = SimpleDocTemplate(stream, pagesize=A4, leftMargin=18*mm, rightMargin=18*mm, topMargin=16*mm, bottomMargin=16*mm)
    styles = getSampleStyleSheet()
    title = ParagraphStyle("PaperTitle", parent=styles["Title"], fontName=font, fontSize=16, leading=20, alignment=TA_CENTER, textColor=colors.HexColor("#073b63"))
    body = ParagraphStyle("PaperBody", parent=styles["BodyText"], fontName=font, fontSize=9.5, leading=13, spaceAfter=5)
    section_style = ParagraphStyle("PaperSection", parent=styles["Heading2"], fontName=font, fontSize=12, leading=15, textColor=colors.HexColor("#086b86"), spaceBefore=12, spaceAfter=6)
    story = [
        Paragraph("CBSE TIMED MOCK TEST", title),
        Paragraph(f"{paper['class']} · {paper['subject']} · Academic session {SESSION}", ParagraphStyle("sub", parent=body, alignment=TA_CENTER)),
    ]
    details = [
        ["Maximum marks", str(paper["total_marks"]), "Duration", "3 hours"],
        ["Paper code", paper["id"], "Date", paper["created"]],
        ["Student name", "________________________________", "Roll no.", "________________"],
    ]
    table = Table(details, colWidths=[28*mm, 53*mm, 26*mm, 53*mm])
    table.setStyle(TableStyle([
        ("FONTNAME",(0,0),(-1,-1),font),("FONTSIZE",(0,0),(-1,-1),8),
        ("BACKGROUND",(0,0),(0,-1),colors.HexColor("#e9f3f7")),
        ("BACKGROUND",(2,0),(2,-1),colors.HexColor("#e9f3f7")),
        ("GRID",(0,0),(-1,-1),.35,colors.HexColor("#9bb4c0")),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6),
    ]))
    story += [Spacer(1,4*mm), table, Paragraph("General Instructions", section_style),
              Paragraph("All questions are compulsory. Attempt only one alternative where an internal choice is given. This is a generated practice paper, not an official CBSE question paper.", body),
              HRFlowable(width="100%", thickness=.6, color=colors.HexColor("#9bb4c0"))]
    current = None
    for number, q in enumerate(paper["questions"], 1):
        if q["section"] != current:
            current = q["section"]
            story.append(Paragraph(f"SECTION {current}", section_style))
        story.append(Paragraph(f"<b>{number}. [{q['marks']} mark(s)]</b> " + para_text(q["prompt"]), body))
        for option in q["options"]:
            story.append(Paragraph(para_text(option), ParagraphStyle("option", parent=body, leftIndent=12)))
        alt = q.get("internal_choice")
        if alt:
            story.append(Paragraph("<b>OR</b>", body))
            story.append(Paragraph(para_text(alt.get("prompt", "")), body))
        story.append(Spacer(1,3*mm))
    story.append(Paragraph("End of question paper · Answer key not included.", ParagraphStyle("end", parent=body, alignment=TA_CENTER)))
    doc.build(story)
    return stream.getvalue()

def chosen_variant(q):
    return st.session_state.get(f"choice_{q['id']}", "A")

def answer_details(q, variant):
    alt = q.get("internal_choice") if variant == "B" else None
    return {
        "id": q["id"], "marks": q["marks"], "prompt": alt["prompt"] if alt else q["prompt"],
        "model_answer": alt.get("model_answer","") if alt else q.get("model_answer",""),
        "marking_points": alt.get("marking_points",[]) if alt else q.get("marking_points",[]),
    }

def score_paper(paper):
    results = {}
    written = []
    for q in paper["questions"]:
        qid = q["id"]
        if q["kind"] in ("mcq","assertion_reason"):
            selected = str(st.session_state.get(f"answer_{qid}", ""))
            expected = re.search(r"\b([A-D])\b", str(q.get("correct_answer","")).upper())
            chosen = re.match(r"\s*([A-D])", selected.upper())
            correct = bool(expected and chosen and expected.group(1) == chosen.group(1))
            results[qid] = {"score":q["marks"] if correct else 0,"max":q["marks"],"response":selected,
                            "feedback":"Correct." if correct else (f"Correct answer: {expected.group(1)}." if expected else "Incorrect.")}
        else:
            variant = chosen_variant(q)
            answer = str(st.session_state.get(f"answer_{qid}_{variant}", "")).strip()
            item = answer_details(q, variant)
            item["student_answer"] = answer
            written.append(item)
            results[qid] = {"score":0,"max":q["marks"],"response":answer,"feedback":"No response submitted." if not answer else ""}
    if written:
        if CLIENT is None:
            raise RuntimeError("Gemini API key is required to score written answers.")
        prompt = """
Mark these answers against the supplied model solutions and marking points.
Award partial marks fairly; never exceed max_marks. Equivalent correct methods count.
Blank or irrelevant answers receive zero. These are provisional AI practice marks.
Return only JSON: {"scores":[{"id":"B1","marks":1.5,"feedback":"Brief reason"}]}
""" + json.dumps(written, ensure_ascii=False)
        response = CLIENT.models.generate_content(
            model=MODEL, contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1, max_output_tokens=6000),
        )
        grades = strip_json_fence(response.text).get("scores", [])
        by_id = {str(g.get("id")):g for g in grades}
        if any(item["id"] not in by_id for item in written):
            raise ValueError("Scoring response was incomplete. Retry scoring.")
        for item in written:
            grade = by_id[item["id"]]
            results[item["id"]]["score"] = max(0,min(float(item["marks"]),float(grade.get("marks",0))))
            results[item["id"]]["feedback"] = str(grade.get("feedback","Marked against the rubric."))
    total = round(sum(float(row["score"]) for row in results.values()),2)
    return {"score":total,"total":paper["total_marks"],"per_question":results}

@st.fragment(run_every="1s")
def timer(deadline):
    remaining=max(0,int(deadline-time.time()))
    minutes,seconds=divmod(remaining,60)
    st.markdown(f'<div class="timer">Time remaining: {minutes:02d}:{seconds:02d}</div>',unsafe_allow_html=True)
    if remaining==0 and st.session_state.exam_status=="running":
        st.session_state.exam_status="scoring"
        st.rerun()

def clear_all():
    for key in list(st.session_state.keys()):
        if key.startswith(("answer_","choice_")) or key in {"exam_status","paper","paper_pdf","started_at","results","grading_error"}:
            st.session_state.pop(key,None)
    st.rerun()

if "exam_status" not in st.session_state: st.session_state.exam_status="setup"
if "paper" not in st.session_state: st.session_state.paper=None
if "paper_pdf" not in st.session_state: st.session_state.paper_pdf=None
if "started_at" not in st.session_state: st.session_state.started_at=None
if "results" not in st.session_state: st.session_state.results=None
if "grading_error" not in st.session_state: st.session_state.grading_error=None

status=st.session_state.exam_status
if status=="setup":
    st.subheader("Choose your mock test")
    col1,col2=st.columns(2)
    with col1: class_name=st.selectbox("Class",CLASSES,key="class_choice")
    with col2: subject=st.selectbox("Subject",SUBJECTS,key="subject_choice")
    st.info(f"Maximum marks: {TOTALS[subject]} · Time allowed: 3 hours")
    if class_name=="Class XII":
        st.caption("Uses current CBSE Class XII sample-paper structure where available.")
    else:
        st.caption("Class XI exams are set by individual schools. This is CBSE-style practice, not one official nationwide paper pattern.")
    st.caption("Each session generates a fresh paper. We do not store a cross-user question history, so exact no-repeat across sessions cannot be guaranteed.")
    st.caption("Written answers receive provisional AI marking. Scores are for practice and are not official.")
    if not API_KEY:
        st.warning("Add GEMINI_API_KEY in Streamlit App settings → Secrets to enable test generation.")
    if st.button("Generate fresh question paper",type="primary",disabled=CLIENT is None):
        with st.spinner("Creating a full mock paper..."):
            try:
                paper=make_paper(class_name,subject)
                st.session_state.paper=paper
                st.session_state.paper_pdf=make_pdf(paper)
                st.session_state.exam_status="ready"
                st.session_state.results=None
                st.rerun()
            except Exception as error:
                st.error(str(error))

elif status=="ready":
    paper=st.session_state.paper
    st.subheader(f"Paper ready · {paper['class']} {paper['subject']}")
    st.write(f"**{paper['total_marks']} marks · 3 hours · Paper {paper['id']}**")
    st.success("Download or print the question paper before starting the timer.")
    st.download_button("Download printable question paper (PDF)",data=st.session_state.paper_pdf,
        file_name=f"CBSE_Mock_{paper['class'].replace(' ','_')}_{paper['subject']}_{paper['id']}.pdf",
        mime="application/pdf",type="primary")
    st.warning("Starting begins the 3-hour timer. You can still download the PDF during the test.")
    if st.button("Start timed test",type="primary"):
        st.session_state.started_at=time.time()
        st.session_state.exam_status="running"
        st.rerun()
    if st.button("Discard paper and generate a different one"):
        st.session_state.paper=None
        st.session_state.paper_pdf=None
        st.session_state.exam_status="setup"
        st.rerun()

elif status=="running":
    paper=st.session_state.paper
    st.subheader(f"{paper['class']} {paper['subject']} · {paper['total_marks']} marks")
    st.caption(f"Paper {paper['id']} · All sections are compulsory · Answers and marks are hidden until submission.")
    timer(float(st.session_state.started_at)+TIME_LIMIT_SECONDS)
    answered=0
    for q in paper["questions"]:
        st.markdown(f"#### {q['id']} · Section {q['section']} · {q['marks']} mark(s)")
        st.markdown(q["prompt"])
        if q["kind"] in ("mcq","assertion_reason"):
            selected=st.radio("Choose one answer",q["options"],index=None,key=f"answer_{q['id']}",label_visibility="collapsed")
            answered += bool(selected)
        else:
            variant="A"
            alt=q.get("internal_choice")
            if alt:
                variant=st.radio("Choose one",["A","B"],format_func=lambda x:"Main question" if x=="A" else "Internal choice",
                    horizontal=True,key=f"choice_{q['id']}")
                st.caption(alt["prompt"] if variant=="B" else q["prompt"])
            text=st.text_area("Write your answer",key=f"answer_{q['id']}_{variant}",height=110 if q["marks"]<=3 else 150,
                placeholder="Type your answer here. Show working for calculations.",label_visibility="collapsed")
            answered += bool(text.strip())
        st.markdown("---")
    st.progress(answered/max(1,len(paper["questions"])),text=f"{answered} of {len(paper['questions'])} answered")
    if st.button("Submit and score test",type="primary"):
        st.session_state.exam_status="scoring"
        st.rerun()

elif status=="scoring":
    paper=st.session_state.paper
    if st.session_state.results is None:
        with st.spinner("Scoring written responses against the marking guide..."):
            try:
                st.session_state.results=score_paper(paper)
                st.session_state.exam_status="finished"
                st.session_state.grading_error=None
                st.rerun()
            except Exception as error:
                st.session_state.grading_error=str(error)
        if st.session_state.grading_error:
            st.error(st.session_state.grading_error)
            if st.button("Retry scoring",type="primary"):
                st.session_state.grading_error=None
                st.rerun()

elif status=="finished":
    paper=st.session_state.paper
    result=st.session_state.results
    score,total=result["score"],result["total"]
    percent=100*score/total
    st.success("Test submitted.")
    c1,c2,c3=st.columns(3)
    c1.metric("Score",f"{score:g} / {total}")
    c2.metric("Percentage",f"{percent:.1f}%")
    c3.metric("Paper code",paper["id"])
    if percent >= 90:
        tier, motivation = "Exceptional", "Outstanding performance! Your preparation is on the right track."
    elif percent >= 75:
        tier, motivation = "Very strong", "Very good result! Keep building on this progress."
    elif percent >= 50:
        tier, motivation = "Developing", "Good effort! Review the questions you missed and keep practising."
    else:
        tier, motivation = "More practice needed", "Don’t be discouraged. Focus on your weaker areas—you can improve."
    st.subheader(f"Performance: {tier}")
    st.write(motivation)
    missed = [
        (q, result["per_question"][q["id"]])
        for q in paper["questions"]
        if result["per_question"][q["id"]]["score"] < result["per_question"][q["id"]]["max"]
    ]
    st.subheader("Questions to review")
    if missed:
        st.caption("These questions were incorrect, unanswered, or received partial marks. See the feedback and suggested answers below.")
        st.write(" · ".join(q["id"] for q, _ in missed))
    else:
        st.success("Full marks on every question—excellent work!")
    st.subheader("Review and suggested answers")
    for q in paper["questions"]:
        row=result["per_question"][q["id"]]
        st.markdown(f"**{q['id']} · {row['score']:g}/{row['max']} marks**")
        if row.get("response"): st.caption(f"Your response: {row['response']}")
        st.write(row.get("feedback",""))
        alt=q.get("internal_choice")
        variant=st.session_state.get(f"choice_{q['id']}","A")
        key=alt if alt and variant=="B" else q
        st.markdown(f"**Suggested answer:** {key.get('model_answer','')}")
        st.markdown("---")
    if st.button("Create another fresh mock test",type="primary"):
        clear_all()
