import json
import os
import re
import smtplib
import traceback
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS", "").strip()
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "").strip()
RESUME_PDF_PATH = os.getenv("RESUME_PDF_PATH", "resume.pdf").strip()
RESUME_PROFILE_PATH = os.getenv("RESUME_PROFILE_PATH", "resume_profile.json").strip()
AUTO_SEND_EMAIL = os.getenv("AUTO_SEND_EMAIL", "true").lower() == "true"
AUTO_SUBMIT_JOB = os.getenv("AUTO_SUBMIT_JOB", "true").lower() == "true"

app = FastAPI(title="Free AI Auto-Apply Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_private_network_and_cors_headers(request: Request, call_next):
    if request.method == "OPTIONS":
        response = JSONResponse(content={"ok": True}, status_code=200)
    else:
        try:
            response = await call_next(request)
        except Exception as exc:
            traceback.print_exc()
            response = JSONResponse(
                status_code=500,
                content={"detail": f"Python Server Error: {str(exc)}"},
            )
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "*"
    response.headers["Access-Control-Allow-Private-Network"] = "true"
    return response


# Pre-configured with Hamza Khan's real details & links
DEFAULT_PROFILE: Dict[str, Any] = {
    "full_name": "Hamza Khan",
    "email": GMAIL_ADDRESS or "your.email@gmail.com",
    "phone": "+92-3212761142",
    "degree": "Bachelor’s degree in Computer Science",
    "portfolio_url": "https://hamzakhan62777.github.io/PortFolioNew/",
    "itch_url": "https://hamza62777.itch.io",
    "linkedin_url": "https://www.linkedin.com/in/thehamza62777",
    "years_of_experience": 2,
    "skills": [
        "Unity (C#)",
        "2D/3D Game Development",
        "OOP",
        "Mobile Game Optimization",
        "Python",
        "AI/ML",
        "Generative AI & LLMs",
        "FastAPI",
        "Git",
    ],
}


def load_resume_profile() -> Dict[str, Any]:
    profile = dict(DEFAULT_PROFILE)
    path = Path(RESUME_PROFILE_PATH)
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                user_data = json.load(f)
            for k, v in user_data.items():
                if v and "yourprofile" not in str(v) and "yourusername" not in str(v) and "0000000" not in str(v):
                    profile[k] = v
        except Exception:
            pass
    return profile


def find_resume_pdf() -> Optional[Path]:
    configured = Path(RESUME_PDF_PATH)
    if configured.exists() and configured.is_file():
        return configured
    pdfs = list(Path(".").glob("*.pdf"))
    return pdfs[0] if pdfs else None


class PostEmailApplyRequest(BaseModel):
    post_text: str
    post_url: Optional[str] = ""
    override_email: Optional[str] = None


class FormQuestionsRequest(BaseModel):
    job_title: Optional[str] = ""
    job_description: Optional[str] = ""
    questions: List[Dict[str, Any]]


EMAIL_REGEX = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"


def extract_company_and_city(post_text: str, recipient_email: str) -> Dict[str, Optional[str]]:
    """Detects company/studio name and city (Lahore, Islamabad, Karachi, etc.) from the post."""
    city = None
    for c in ["Lahore", "Islamabad", "Rawalpindi", "Karachi", "Faisalabad", "Peshawar", "Multan"]:
        if re.search(rf"\b{c}\b", post_text, re.IGNORECASE):
            city = c
            break

    company = None
    comp_match = re.search(
        r"\b(?:at|join|with)\s+([A-Z][A-Za-z0-9\s&]{2,30}?(?:Studio|Studios|Games|Gaming|Tech|Technologies|Solutions|Labs|AI|Digital|Systems|Interactive|Soft|Software))\b",
        post_text,
    )
    if comp_match:
        company = " ".join(comp_match.group(1).split()).strip()

    return {"company": company, "city": city}


def extract_role_and_tailor_email(
    post_text: str, profile: Dict[str, Any], recipient_email: str
) -> Dict[str, str]:
    full_name = profile.get("full_name", "Hamza Khan")
    phone = profile.get("phone", "+92-3212761142")
    portfolio_url = profile.get("portfolio_url", "https://hamzakhan62777.github.io/PortFolioNew/")
    itch_url = profile.get("itch_url", "https://hamza62777.itch.io")
    linkedin_url = profile.get("linkedin_url", "https://www.linkedin.com/in/thehamza62777")

    text_lower = post_text.lower()
    is_internship = bool(
        re.search(r"\b(intern|internship|internee|trainee|fresh graduate|fellowship)\b", text_lower)
    )

    meta = extract_company_and_city(post_text, recipient_email)
    company = meta["company"]
    city = meta["city"]

    # 1. Check if the post explicitly demands a specific Subject Line
    explicit_subject = None
    subj_match = re.search(
        r"(?:subject\s*(?:line)?\s*(?:should\s*be|as|is|:|-))\s*[\"“']?([^\"\n\r”']{4,70})[\"”']?",
        post_text,
        re.IGNORECASE,
    )
    if subj_match:
        candidate_subj = subj_match.group(1).strip(" .,-:")
        candidate_subj = re.sub(r"\[.*?name.*?\]|<.*?name.*?>", full_name, candidate_subj, flags=re.I)
        if len(candidate_subj) >= 4:
            explicit_subject = candidate_subj

    # 2. Extract the exact job title mentioned in the post
    extracted_title = None
    title_patterns = [
        r"\b((?:Senior\s+|Junior\s+|Lead\s+|Associate\s+|Trainee\s+)?(?:Unity|Game|Unreal|C#|AI|ML|Machine Learning|GenAI|Generative AI|Data Science|Data|Python|Backend|Full\s*Stack|Software|Django|FastAPI|Automation|MERN|React|Frontend|Mobile)\s+(?:Game\s+|Backend\s+|Software\s+)?(?:Developer\s+Intern|Engineer\s+Intern|Intern|Internship|Trainee|Developer|Engineer|Programmer|Specialist|Analyst))\b",
        r"(?:hiring|looking\s+for|seeking|opening\s+for|position\s*:|role\s*:|title\s*:|vacancy\s+for)\s+(?:an\s+|a\s+|the\s+)?([A-Za-z0-9\s/\-&+#]{3,40}?(?:Developer\s+Intern|Engineer\s+Intern|Intern|Internship|Trainee|Developer|Engineer|Designer|Programmer|Specialist|Analyst))\b",
    ]
    for pat in title_patterns:
        m = re.search(pat, post_text, re.IGNORECASE)
        if m:
            raw_title = " ".join(m.group(1).split()).strip(" -:,.")
            raw_title = re.sub(r"^(?:an|a|the|for|as)\s+", "", raw_title, flags=re.I).strip()
            if 3 <= len(raw_title) <= 50:
                extracted_title = raw_title
                break

    # 3. Detect the Job Category from post keywords
    game_score = len(
        re.findall(r"\b(unity|unity3d|game|games|gaming|c#|unreal|gameplay|2d|3d|shader|phaser|godot|hypercasual|mobile game)\b", text_lower)
    )
    ai_score = len(
        re.findall(r"\b(ai|artificial intelligence|machine learning|ml|deep learning|llm|llms|genai|generative ai|nlp|computer vision|rag|langchain|agent|agentic|pytorch|tensorflow|openai)\b", text_lower)
    )
    python_score = len(
        re.findall(r"\b(python|django|fastapi|flask|backend|rest api|automation|scraping|playwright|selenium|sql|postgresql)\b", text_lower)
    )

    greeting = f"Dear Hiring Team at {company}," if company else "Dear Hiring Team,"
    location_phrase = f" at your {city} office" if city else ""

    if game_score > ai_score and game_score >= python_score and game_score > 0:
        category = "game"
        default_role = "Unity Game Developer Intern" if is_internship else "Unity Game Developer"
        final_role = extracted_title or default_role
        if is_internship and not re.search(r"\b(intern|internship|trainee)\b", final_role, re.I):
            final_role = f"{final_role} Intern"

        opening = (
            f"I am writing to express my strong interest in the {final_role} position{location_phrase}. "
            f"Holding a Bachelor’s degree in Computer Science paired with hands-on experience engineering, optimizing, and deploying 2D/3D games using Unity (C#), I am excited about the opportunity to join your team."
        )
        bullets = (
            "Key Qualifications & Technical Capabilities:\n"
            "- Core Unity & C# Architecture: Proficient in object-oriented programming (OOP), custom gameplay mechanics, dynamic state patterns, object pooling, and physics scripting.\n"
            "- Mobile Game Optimization: Skilled in profiling frame rates (targeting a smooth 60 FPS), draw call batching, memory management, and fixing performance bottlenecks for mobile devices.\n"
            "- UI & Asset Integration: Experienced in implementing responsive UI systems, handling animation pipelines, and debugging gameplay systems efficiently."
        )
        links_section = (
            "Portfolio & Professional Links:\n"
            f"- Interactive Portfolio: {portfolio_url}\n"
            f"- Playable Demos & Builds: {itch_url}\n"
            f"- LinkedIn Profile: {linkedin_url}"
        )

    elif ai_score >= game_score and ai_score > 0:
        category = "ai"
        default_role = "AI Engineer Intern" if is_internship else "AI / Machine Learning Engineer"
        final_role = extracted_title or default_role
        if is_internship and not re.search(r"\b(intern|internship|trainee)\b", final_role, re.I):
            final_role = f"{final_role} Intern"

        opening = (
            f"I am writing to express my strong interest in the {final_role} position{location_phrase}. "
            f"Holding a Bachelor’s degree in Computer Science paired with hands-on experience building AI-powered applications, LLM agents, and intelligent Python workflows, I am excited about the opportunity to join your team."
        )
        bullets = (
            "Key Qualifications & Technical Capabilities:\n"
            "- Applied AI & LLM Engineering: Proficient in building AI agents, RAG pipelines, prompt engineering, and integrating LLM APIs (Gemini, OpenAI) into real-world applications.\n"
            "- Machine Learning & Python Architecture: Skilled in Python, data processing pipelines, intelligent automation, and writing clean, modular object-oriented code.\n"
            "- Backend & API Deployment: Experienced in serving AI models and automation workflows through scalable FastAPI and RESTful API services."
        )
        links_section = (
            "Portfolio & Professional Links:\n"
            f"- Interactive Portfolio: {portfolio_url}\n"
            f"- LinkedIn Profile: {linkedin_url}\n"
            f"- Interactive Projects & Demos: {itch_url}"
        )

    elif python_score > 0:
        category = "python"
        default_role = "Python Developer Intern" if is_internship else "Python Developer"
        final_role = extracted_title or default_role
        if is_internship and not re.search(r"\b(intern|internship|trainee)\b", final_role, re.I):
            final_role = f"{final_role} Intern"

        opening = (
            f"I am writing to express my strong interest in the {final_role} position{location_phrase}. "
            f"Holding a Bachelor’s degree in Computer Science paired with hands-on experience developing scalable Python backends, REST APIs, and automation systems, I am excited about the opportunity to join your team."
        )
        bullets = (
            "Key Qualifications & Technical Capabilities:\n"
            "- Core Python & Backend Engineering: Proficient in object-oriented programming (OOP), FastAPI, Django/Flask, RESTful API design, and clean backend architecture.\n"
            "- Automation & System Integration: Skilled in building end-to-end automation tools, browser/API integrations, and efficient data handling with SQL.\n"
            "- Problem Solving & Delivery: Strong Computer Science fundamentals in data structures, debugging, Git version control, and writing maintainable production code."
        )
        links_section = (
            "Portfolio & Professional Links:\n"
            f"- Interactive Portfolio: {portfolio_url}\n"
            f"- LinkedIn Profile: {linkedin_url}\n"
            f"- Additional Projects: {itch_url}"
        )

    else:
        category = "general"
        default_role = "Software Engineer Intern" if is_internship else "Software Engineer"
        final_role = extracted_title or default_role
        if is_internship and not re.search(r"\b(intern|internship|trainee)\b", final_role, re.I):
            final_role = f"{final_role} Intern"

        opening = (
            f"I am writing to express my strong interest in the {final_role} position{location_phrase}. "
            f"Holding a Bachelor’s degree in Computer Science paired with hands-on experience in full-lifecycle software development, Python/C# engineering, and interactive applications, I am excited about the opportunity to join your team."
        )
        bullets = (
            "Key Qualifications & Technical Capabilities:\n"
            "- Software & Application Engineering: Proficient in object-oriented programming (OOP) using C# and Python, modular architecture, and clean design patterns.\n"
            "- Backend, AI & Interactive Systems: Experienced in building REST APIs, intelligent automation workflows, and responsive user-facing applications.\n"
            "- Performance & Debugging: Skilled in profiling performance bottlenecks, memory management, Git version control, and collaborative agile development."
        )
        links_section = (
            "Portfolio & Professional Links:\n"
            f"- Interactive Portfolio: {portfolio_url}\n"
            f"- Playable Demos & Builds: {itch_url}\n"
            f"- LinkedIn Profile: {linkedin_url}"
        )

    company_closing = f"{company}'s upcoming projects" if company else "your team's upcoming projects"
    if city and city.lower() != "karachi":
        closing = (
            f"My resume is attached for your review. I am fully prepared for immediate relocation to {city} for this role "
            f"and look forward to discussing how my background aligns with {company_closing}."
        )
    else:
        closing = (
            f"My resume is attached for your review. I am available for an immediate start "
            f"and look forward to discussing how my background aligns with {company_closing}."
        )

    subject = explicit_subject or f"Application for {final_role} - {full_name}"

    body = (
        f"{greeting}\n\n"
        f"{opening}\n\n"
        f"{bullets}\n\n"
        f"{links_section}\n\n"
        f"{closing}\n\n"
        f"Best regards,\n"
        f"{full_name}\n"
        f"Phone: {phone}"
    )

    return {
        "recipient_email": recipient_email,
        "subject": subject,
        "body": body,
        "detected_role": final_role,
        "detected_category": category,
    }


def generate_tailored_email(post_text: str, profile: Dict[str, Any], default_email: str) -> Dict[str, str]:
    structured_draft = extract_role_and_tailor_email(post_text, profile, default_email)

    if not GEMINI_API_KEY or "your_free" in GEMINI_API_KEY.lower():
        return structured_draft

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=GEMINI_API_KEY)
        full_name = profile.get("full_name", "Hamza Khan")
        phone = profile.get("phone", "+92-3212761142")
        portfolio_url = profile.get("portfolio_url", "https://hamzakhan62777.github.io/PortFolioNew/")
        itch_url = profile.get("itch_url", "https://hamza62777.itch.io")
        linkedin_url = profile.get("linkedin_url", "https://www.linkedin.com/in/thehamza62777")

        prompt = f"""
You are writing a formal, high-impact job application email for {full_name} based on the LinkedIn hiring post below.

Follow this EXACT structure and level of detail (adapt the role title, company name, city/relocation note, and the 3 technical bullets to match ONLY the specific job in the post — Game Dev vs. AI/ML vs. Python/Software vs. Internship):

TEMPLATE STRUCTURE TO FOLLOW:
Dear Hiring Team [at Company Name if mentioned],

I am writing to express my strong interest in the [Exact Role Title] position [at your City office if mentioned]. Holding a Bachelor’s degree in Computer Science paired with hands-on experience [1-line summary matching ONLY the post's domain], I am excited about the opportunity to join your team.

Key Qualifications & Technical Capabilities:
- [Skill Area 1 relevant to post]: [Detailed 1-sentence capability]
- [Skill Area 2 relevant to post]: [Detailed 1-sentence capability]
- [Skill Area 3 relevant to post]: [Detailed 1-sentence capability]

Portfolio & Professional Links:
- Interactive Portfolio: {portfolio_url}
- Playable Demos & Builds: {itch_url}
- LinkedIn Profile: {linkedin_url}

My resume is attached for your review. [If post mentions a city outside Karachi like Lahore/Islamabad, state: "I am fully prepared for immediate relocation to [City] for this role and"] I look forward to discussing how my background aligns with [Company Name's / your team's] upcoming projects.

Best regards,
{full_name}
Phone: {phone}

STRICT RULES:
1. Never mix Unity/Game Dev with AI/Python unless the post asks for both. If the post is for Game Dev, write all 3 bullets about Unity (C#), OOP/gameplay mechanics, mobile 60 FPS optimization, and UI/animation pipelines. If the post is for AI, Python, or an Internship, write all 3 bullets specifically for that role.
2. If the post specifies a required Subject Line format, follow it strictly. Otherwise use: "Application for [Exact Role in Post] - {full_name}".
3. Return ONLY valid JSON with keys: "recipient_email", "subject", "body".

LINKEDIN POST:
{post_text}
"""
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2,
            ),
        )
        ai_res = json.loads(response.text)
        if ai_res.get("subject") and ai_res.get("body"):
            return ai_res
        return structured_draft
    except Exception as e:
        print(f"[Info] Using structured role-specific template ({e})")
        return structured_draft


def send_email_with_resume(to_email: str, subject: str, body: str, profile: Dict[str, Any]) -> str:
    if not GMAIL_ADDRESS or "your.email" in GMAIL_ADDRESS:
        raise ValueError("Set your real GMAIL_ADDRESS inside your .env file!")
    if not GMAIL_APP_PASSWORD or "xxxx" in GMAIL_APP_PASSWORD or "your_16_char" in GMAIL_APP_PASSWORD:
        raise ValueError("Set your 16-character GMAIL_APP_PASSWORD inside your .env file!")

    msg = EmailMessage()
    msg["From"] = f"{profile.get('full_name', 'Hamza Khan')} <{GMAIL_ADDRESS}>"
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    resume_path = find_resume_pdf()
    attached_note = "(No PDF found in folder, sent without attachment)"
    if resume_path:
        with open(resume_path, "rb") as f:
            pdf_data = f.read()
        msg.add_attachment(
            pdf_data,
            maintype="application",
            subtype="pdf",
            filename=resume_path.name,
        )
        attached_note = f"(Attached: {resume_path.name})"

    clean_app_password = GMAIL_APP_PASSWORD.replace(" ", "").replace('"', "").replace("'", "")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(GMAIL_ADDRESS, clean_app_password)
        smtp.send_message(msg)

    return attached_note


@app.post("/apply-email")
async def apply_to_post_via_email(req: PostEmailApplyRequest):
    try:
        profile = load_resume_profile()
        found_emails = re.findall(EMAIL_REGEX, req.post_text or "")
        default_email = req.override_email or (found_emails[0] if found_emails else "")

        ai_draft = generate_tailored_email(req.post_text, profile, default_email)
        target_email = (
            req.override_email
            or (found_emails[0] if found_emails else None)
            or ai_draft.get("recipient_email")
        )

        if not target_email or "@" not in target_email:
            return JSONResponse(
                status_code=422,
                content={
                    "detail": "No email address found in the selected post text. Make sure the post contains an email like hr@company.com!"
                },
            )

        subject = ai_draft.get("subject", f"Job Application - {profile.get('full_name', 'Hamza Khan')}")
        body = ai_draft.get("body", "")

        if AUTO_SEND_EMAIL:
            attach_info = send_email_with_resume(target_email, subject, body, profile)
            status_msg = f"Email sent to {target_email} {attach_info}"
        else:
            status_msg = f"Preview mode: Draft ready for {target_email}"

        print(f"[SUCCESS] {status_msg} | Subject: {subject}")
        return {
            "status": "success",
            "message": status_msg,
            "recipient": target_email,
            "subject": subject,
            "body": body,
        }
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=400, content={"detail": str(e)})


if __name__ == "__main__":
    import uvicorn

    print("============================================================")
    print(" Free AI Auto-Apply Backend Running on http://127.0.0.1:8000")
    print("============================================================")
    uvicorn.run(app, host="127.0.0.1", port=8000)