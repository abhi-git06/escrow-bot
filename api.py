import os
import json as json_lib
import random
import string
import hmac
import hashlib
import time
import httpx
import uuid
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# Groq client
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Allow frontend to talk to backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared storage
escrows = {}
reputation = {}

# ─────────────────────────────────────────
# Models
# ─────────────────────────────────────────
class JobRequest(BaseModel):
    description: str
    amount: str
    deadline: str
    client: str = "web_user"

class JobUpdate(BaseModel):
    score: Optional[float] = None
    status: Optional[str] = None
    verdict: Optional[str] = None
    reasoning: Optional[str] = None
    freelancer: Optional[str] = None

class WorkSubmission(BaseModel):
    work: str
    freelancer: str = "anonymous"

class DisputeRequest(BaseModel):
    reason: str
    raised_by: str = "anonymous"

# ─────────────────────────────────────────
# x402 Demo Mode
# ─────────────────────────────────────────
def create_x402_order(amount: str, job_id: str, description: str, from_address: str = "0x0000000000000000000000000000000000000000") -> dict:
    # Demo mode — x402 integration ready, pending fee balance top-up
    print(f"[DEMO MODE] Creating order for job {job_id}: {amount} USDC")
    return {
        "order_id": f"order_{job_id}",
        "payment_url": f"https://explorer.testnet3.goat.network/address/0x4BcDb92958F8475c0503bfB5BC6e34De5D6F3CE6",
        "pay_to_address": "0x4BcDb92958F8475c0503bfB5BC6e34De5D6F3CE6"
    }

# ─────────────────────────────────────────
# Reputation helpers
# ─────────────────────────────────────────
def update_reputation(username: str, score: float, verdict: str):
    if username not in reputation:
        reputation[username] = {
            "total_jobs": 0,
            "total_score": 0,
            "avg_score": 0,
            "completed": 0,
            "rejected": 0
        }
    r = reputation[username]
    r["total_jobs"] += 1
    r["total_score"] += score
    r["avg_score"] = round(r["total_score"] / r["total_jobs"], 1)
    if verdict == "REJECT":
        r["rejected"] += 1
    else:
        r["completed"] += 1

# ─────────────────────────────────────────
# Routes
# ─────────────────────────────────────────

@app.get("/api/jobs")
def get_jobs():
    return {"jobs": escrows}

@app.post("/api/jobs")
def create_job(job: JobRequest):
    job_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    order = create_x402_order(job.amount, job_id, job.description)
    created_at = int(time.time())
    deadline_seconds = int(float(job.deadline) * 3600)

    escrows[job_id] = {
        "description": job.description,
        "amount": job.amount,
        "deadline": job.deadline,
        "deadline_at": created_at + deadline_seconds,
        "created_at": created_at,
        "client": job.client,
        "status": "open",
        "order_id": order["order_id"],
        "payment_url": order["payment_url"],
        "pay_to_address": order.get("pay_to_address", ""),
        "score": None,
        "verdict": None,
        "reasoning": None,
        "freelancer": None,
        "dispute": None
    }

    return {
        "success": True,
        "job_id": job_id,
        "order_id": order["order_id"],
        "payment_url": order["payment_url"],
        "pay_to_address": order.get("pay_to_address", "")
    }

@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    if job_id not in escrows:
        return {"error": "Job not found"}
    return escrows[job_id]

@app.patch("/api/jobs/{job_id}")
def update_job(job_id: str, update: JobUpdate):
    if job_id not in escrows:
        return {"error": "Job not found"}
    if update.score is not None:
        escrows[job_id]['score'] = update.score
    if update.status is not None:
        escrows[job_id]['status'] = update.status
    if update.verdict is not None:
        escrows[job_id]['verdict'] = update.verdict
    if update.reasoning is not None:
        escrows[job_id]['reasoning'] = update.reasoning
    if update.freelancer is not None:
        escrows[job_id]['freelancer'] = update.freelancer
    return {"success": True}

@app.post("/api/jobs/{job_id}/submit")
def submit_work(job_id: str, submission: WorkSubmission):
    if job_id not in escrows:
        return {"error": "Job not found"}

    job = escrows[job_id]

    if job['status'] != 'open':
        return {"error": f"Job is already {job['status']}"}

    # Check deadline
    if int(time.time()) > job.get('deadline_at', float('inf')):
        escrows[job_id]['status'] = 'expired'
        return {"error": "Job deadline has passed"}

    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{
                "role": "user",
                "content": f"""You are a fair freelance work arbitrator.

Job Description: {job['description']}

Submitted Work: {submission.work}

Evaluate the submitted work strictly and fairly.
Respond ONLY in this JSON format with no extra text:
{{
  "score": <1-10>,
  "payment_percentage": <0-100>,
  "reasoning": "<brief explanation>",
  "verdict": "<APPROVE | PARTIAL | REJECT>"
}}

Score guide:
- 9-10: Excellent, pay 100%
- 7-8: Good, pay 85%
- 5-6: Acceptable, pay 60%
- 3-4: Poor, pay 30%
- 1-2: Unacceptable, refund client"""
            }],
            temperature=0.1
        )

        result = json_lib.loads(response.choices[0].message.content)

    except Exception as e:
        return {"error": f"AI evaluation failed: {str(e)}"}

    # Update escrow
    escrows[job_id]['score'] = result['score']
    escrows[job_id]['verdict'] = result['verdict']
    escrows[job_id]['reasoning'] = result['reasoning']
    escrows[job_id]['submitted_work'] = submission.work
    escrows[job_id]['freelancer'] = submission.freelancer
    escrows[job_id]['status'] = 'completed' if result['verdict'] != 'REJECT' else 'refunded'

    # Update reputation
    update_reputation(submission.freelancer, result['score'], result['verdict'])

    payment_released = float(job['amount']) * result['payment_percentage'] / 100

    return {
        "success": True,
        "score": result['score'],
        "verdict": result['verdict'],
        "reasoning": result['reasoning'],
        "payment_percentage": result['payment_percentage'],
        "payment_released": round(payment_released, 2)
    }

@app.post("/api/jobs/{job_id}/dispute")
def raise_dispute(job_id: str, dispute: DisputeRequest):
    if job_id not in escrows:
        return {"error": "Job not found"}

    job = escrows[job_id]

    if job['status'] not in ['completed', 'refunded']:
        return {"error": "Can only dispute completed or refunded jobs"}

    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{
                "role": "user",
                "content": f"""You are a senior freelance work arbitrator handling a dispute.

Job Description: {job['description']}

Submitted Work: {job.get('submitted_work', 'Not available')}

Original AI Score: {job.get('score')}/10
Original Verdict: {job.get('verdict')}
Original Reasoning: {job.get('reasoning')}

Dispute Raised By: {dispute.raised_by}
Dispute Reason: {dispute.reason}

Re-evaluate carefully considering the dispute reason.
Respond ONLY in this JSON format with no extra text:
{{
  "score": <1-10>,
  "payment_percentage": <0-100>,
  "reasoning": "<detailed explanation considering the dispute>",
  "verdict": "<APPROVE | PARTIAL | REJECT>",
  "dispute_outcome": "<UPHELD | DENIED>",
  "dispute_explanation": "<why the dispute was upheld or denied>"
}}"""
            }],
            temperature=0.1
        )

        result = json_lib.loads(response.choices[0].message.content)

    except Exception as e:
        return {"error": f"AI re-evaluation failed: {str(e)}"}

    escrows[job_id]['dispute'] = {
        "reason": dispute.reason,
        "raised_by": dispute.raised_by,
        "outcome": result['dispute_outcome'],
        "explanation": result['dispute_explanation'],
        "new_score": result['score'],
        "new_verdict": result['verdict']
    }
    escrows[job_id]['score'] = result['score']
    escrows[job_id]['verdict'] = result['verdict']
    escrows[job_id]['reasoning'] = result['reasoning']
    escrows[job_id]['status'] = 'disputed'

    payment_released = float(job['amount']) * result['payment_percentage'] / 100

    return {
        "success": True,
        "dispute_outcome": result['dispute_outcome'],
        "dispute_explanation": result['dispute_explanation'],
        "new_score": result['score'],
        "new_verdict": result['verdict'],
        "new_reasoning": result['reasoning'],
        "payment_released": round(payment_released, 2)
    }

@app.get("/api/reputation/{username}")
def get_reputation(username: str):
    if username not in reputation:
        return {
            "username": username,
            "total_jobs": 0,
            "avg_score": 0,
            "completed": 0,
            "rejected": 0,
            "level": "New"
        }
    r = reputation[username]
    avg = r['avg_score']
    level = "🏆 Elite" if avg >= 9 else "⭐ Expert" if avg >= 7 else "👍 Good" if avg >= 5 else "⚠️ Needs Improvement"
    return {
        "username": username,
        **r,
        "level": level
    }

@app.get("/api/leaderboard")
def get_leaderboard():
    if not reputation:
        return {"leaderboard": []}
    sorted_rep = sorted(reputation.items(), key=lambda x: x[1]['avg_score'], reverse=True)
    leaderboard = []
    for i, (username, data) in enumerate(sorted_rep[:10]):
        avg = data['avg_score']
        level = "🏆 Elite" if avg >= 9 else "⭐ Expert" if avg >= 7 else "👍 Good" if avg >= 5 else "⚠️ Needs Improvement"
        leaderboard.append({
            "rank": i + 1,
            "username": username,
            "avg_score": data['avg_score'],
            "total_jobs": data['total_jobs'],
            "completed": data['completed'],
            "level": level
        })
    return {"leaderboard": leaderboard}

@app.get("/api/history/{username}")
def get_history(username: str):
    user_jobs = {
        k: v for k, v in escrows.items()
        if v.get('client') == username or v.get('freelancer') == username
    }
    return {"history": user_jobs}

@app.get("/api/stats")
def get_stats():
    total = len(escrows)
    open_jobs = len([j for j in escrows.values() if j["status"] == "open"])
    completed = len([j for j in escrows.values() if j["status"] == "completed"])
    refunded = len([j for j in escrows.values() if j["status"] == "refunded"])
    disputed = len([j for j in escrows.values() if j["status"] == "disputed"])
    total_usdc = sum(float(j["amount"]) for j in escrows.values())
    return {
        "total": total,
        "open": open_jobs,
        "completed": completed,
        "refunded": refunded,
        "disputed": disputed,
        "total_usdc": round(total_usdc, 2)
    }

# Serve static files — must be last!
app.mount("/", StaticFiles(directory="static", html=True), name="static")