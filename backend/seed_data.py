"""Seed realistic per-clinic veterinary demo data."""
from datetime import datetime, timezone, timedelta
import uuid


def _id():
    return str(uuid.uuid4())


def _iso(dt):
    return dt.isoformat()


def build_seed(clinic_id: str = "demo"):
    NOW = datetime.now(timezone.utc)

    owners = [
        {"id": _id(), "clinic_id": clinic_id, "name": "Amelia Fischer", "email": "amelia.f@example.com", "phone": "(415) 555-0142", "language": "English"},
        {"id": _id(), "clinic_id": clinic_id, "name": "Marcus Chen", "email": "marcus.c@example.com", "phone": "(415) 555-0178", "language": "English"},
        {"id": _id(), "clinic_id": clinic_id, "name": "Sofia Ruiz", "email": "sofia.r@example.com", "phone": "(415) 555-0193", "language": "Spanish"},
        {"id": _id(), "clinic_id": clinic_id, "name": "Priya Nair", "email": "priya.n@example.com", "phone": "(415) 555-0211", "language": "English"},
    ]

    patients = [
        {"id": _id(), "clinic_id": clinic_id, "name": "Bella", "species": "Canine", "breed": "Golden Retriever", "age_years": 7, "sex": "Spayed Female", "weight_kg": 32.4, "microchip": "985141005512334", "owner_id": owners[0]["id"], "active_problems": ["Atopic dermatitis", "Otitis externa (chronic)"], "alerts": ["Overdue: Rabies booster"]},
        {"id": _id(), "clinic_id": clinic_id, "name": "Milo", "species": "Feline", "breed": "Domestic Shorthair", "age_years": 12, "sex": "Neutered Male", "weight_kg": 4.1, "microchip": "985141005519087", "owner_id": owners[1]["id"], "active_problems": ["Chronic kidney disease (IRIS Stage 2)"], "alerts": ["Elevated SDMA — trend up"]},
        {"id": _id(), "clinic_id": clinic_id, "name": "Luna", "species": "Canine", "breed": "French Bulldog", "age_years": 3, "sex": "Intact Female", "weight_kg": 11.8, "microchip": "985141005520114", "owner_id": owners[2]["id"], "active_problems": ["Grade 2 medial patellar luxation (L)"], "alerts": []},
        {"id": _id(), "clinic_id": clinic_id, "name": "Ollie", "species": "Canine", "breed": "Labrador Retriever", "age_years": 5, "sex": "Neutered Male", "weight_kg": 34.7, "microchip": "985141005525999", "owner_id": owners[3]["id"], "active_problems": ["Post-op TPLO (R stifle) — Day 10"], "alerts": ["Recheck due in 4 days"]},
    ]

    visits = [
        {"id": _id(), "clinic_id": clinic_id, "patient_id": patients[0]["id"], "date": _iso(NOW - timedelta(days=45)), "reason": "Recheck otitis externa", "type": "Dermatology", "signed": True, "vet": "Dr. Reyes"},
        {"id": _id(), "clinic_id": clinic_id, "patient_id": patients[0]["id"], "date": _iso(NOW - timedelta(days=180)), "reason": "Annual wellness", "type": "Wellness", "signed": True, "vet": "Dr. Reyes"},
        {"id": _id(), "clinic_id": clinic_id, "patient_id": patients[1]["id"], "date": _iso(NOW - timedelta(days=30)), "reason": "CKD monitoring bloodwork", "type": "Internal medicine", "signed": True, "vet": "Dr. Okafor"},
        {"id": _id(), "clinic_id": clinic_id, "patient_id": patients[1]["id"], "date": _iso(NOW - timedelta(days=120)), "reason": "Weight loss workup", "type": "Internal medicine", "signed": True, "vet": "Dr. Okafor"},
        {"id": _id(), "clinic_id": clinic_id, "patient_id": patients[2]["id"], "date": _iso(NOW - timedelta(days=10)), "reason": "Intermittent left hind lameness", "type": "Orthopedics", "signed": True, "vet": "Dr. Reyes"},
        {"id": _id(), "clinic_id": clinic_id, "patient_id": patients[3]["id"], "date": _iso(NOW - timedelta(days=10)), "reason": "TPLO surgery — R stifle", "type": "Surgery", "signed": True, "vet": "Dr. Okafor"},
    ]

    labs = [
        {"id": _id(), "clinic_id": clinic_id, "patient_id": patients[1]["id"], "date": _iso(NOW - timedelta(days=180)), "creatinine": 1.6, "bun": 28, "sdma": 14, "phosphorus": 4.2, "usg": 1.028},
        {"id": _id(), "clinic_id": clinic_id, "patient_id": patients[1]["id"], "date": _iso(NOW - timedelta(days=120)), "creatinine": 1.9, "bun": 32, "sdma": 16, "phosphorus": 4.6, "usg": 1.021},
        {"id": _id(), "clinic_id": clinic_id, "patient_id": patients[1]["id"], "date": _iso(NOW - timedelta(days=60)), "creatinine": 2.2, "bun": 38, "sdma": 19, "phosphorus": 5.1, "usg": 1.017},
        {"id": _id(), "clinic_id": clinic_id, "patient_id": patients[1]["id"], "date": _iso(NOW - timedelta(days=30)), "creatinine": 2.5, "bun": 42, "sdma": 22, "phosphorus": 5.4, "usg": 1.015},
    ]

    weights = [
        {"id": _id(), "clinic_id": clinic_id, "patient_id": patients[0]["id"], "date": _iso(NOW - timedelta(days=365)), "weight_kg": 30.1},
        {"id": _id(), "clinic_id": clinic_id, "patient_id": patients[0]["id"], "date": _iso(NOW - timedelta(days=180)), "weight_kg": 31.2},
        {"id": _id(), "clinic_id": clinic_id, "patient_id": patients[0]["id"], "date": _iso(NOW - timedelta(days=45)), "weight_kg": 32.0},
        {"id": _id(), "clinic_id": clinic_id, "patient_id": patients[0]["id"], "date": _iso(NOW), "weight_kg": 32.4},
        {"id": _id(), "clinic_id": clinic_id, "patient_id": patients[1]["id"], "date": _iso(NOW - timedelta(days=365)), "weight_kg": 5.2},
        {"id": _id(), "clinic_id": clinic_id, "patient_id": patients[1]["id"], "date": _iso(NOW - timedelta(days=180)), "weight_kg": 4.8},
        {"id": _id(), "clinic_id": clinic_id, "patient_id": patients[1]["id"], "date": _iso(NOW - timedelta(days=60)), "weight_kg": 4.3},
        {"id": _id(), "clinic_id": clinic_id, "patient_id": patients[1]["id"], "date": _iso(NOW - timedelta(days=30)), "weight_kg": 4.1},
    ]

    appointments = []
    today = NOW.replace(hour=8, minute=0, second=0, microsecond=0)
    slots = [
        (patients[0], "09:00", "Recheck — chronic otitis", "Dermatology recheck", "Dr. Reyes", "Room 2"),
        (patients[1], "10:30", "CKD progress bloodwork", "Internal medicine", "Dr. Okafor", "Room 1"),
        (patients[2], "13:00", "Orthopedic consult — patellar luxation", "Orthopedics", "Dr. Reyes", "Room 3"),
        (patients[3], "15:30", "Post-op recheck Day 10", "Post-op", "Dr. Okafor", "Room 1"),
    ]
    for pat, time_str, reason, apt_type, vet, room in slots:
        h, m = time_str.split(":")
        dt = today.replace(hour=int(h), minute=int(m))
        appointments.append({
            "id": _id(), "clinic_id": clinic_id, "patient_id": pat["id"],
            "datetime": _iso(dt), "reason": reason, "type": apt_type,
            "vet": vet, "room": room, "status": "scheduled",
        })

    messages = [
        {"id": _id(), "clinic_id": clinic_id, "owner_id": owners[0]["id"], "patient_id": patients[0]["id"], "received_at": _iso(NOW - timedelta(hours=2)), "channel": "Portal", "subject": "Bella scratching her ears again", "body": "Hi, Bella has been shaking her head and scratching her right ear a lot since yesterday. She finished the last course of drops two weeks ago. Should I bring her in?", "status": "new", "category": "appointment_needed", "draft": None},
        {"id": _id(), "clinic_id": clinic_id, "owner_id": owners[3]["id"], "patient_id": patients[3]["id"], "received_at": _iso(NOW - timedelta(hours=5)), "channel": "SMS", "subject": "Ollie licking incision", "body": "Ollie keeps trying to lick his TPLO incision even with the cone on. It looks slightly pink around the edges but no discharge. Is this normal at day 10?", "status": "new", "category": "medication_question", "draft": None},
        {"id": _id(), "clinic_id": clinic_id, "owner_id": owners[1]["id"], "patient_id": patients[1]["id"], "received_at": _iso(NOW - timedelta(hours=8)), "channel": "Email", "subject": "Refill request — benazepril", "body": "Hello, we're almost out of Milo's benazepril (2.5mg once daily). Could you refill it? Thanks!", "status": "new", "category": "refill_request", "draft": None},
        {"id": _id(), "clinic_id": clinic_id, "owner_id": owners[2]["id"], "patient_id": patients[2]["id"], "received_at": _iso(NOW - timedelta(days=1)), "channel": "Portal", "subject": "Luna's limp", "body": "Luna's limp comes and goes. She was running at the park yesterday and then held her leg up for about a minute. She seems fine now. What should we do?", "status": "new", "category": "appointment_needed", "draft": None},
    ]

    tasks = [
        {"id": _id(), "clinic_id": clinic_id, "patient_id": patients[3]["id"], "title": f"Post-op check-in call — {patients[3]['name']}", "description": "Confirm suture removal readiness; verify weight-bearing and controlled activity.", "priority": "high", "status": "open", "source": "auto_postop", "source_id": f"postop_{patients[3]['id']}", "created_at": _iso(NOW - timedelta(days=1)), "due_date": _iso(NOW + timedelta(days=1)), "completed_at": None},
        {"id": _id(), "clinic_id": clinic_id, "patient_id": patients[1]["id"], "title": f"Monitoring due — {patients[1]['name']} (Chronic kidney disease (IRIS Stage 2))", "description": "Renal panel + urinalysis, blood pressure recheck.", "priority": "normal", "status": "open", "source": "auto_chronic", "source_id": f"chronic_{patients[1]['id']}_Chronic kidn", "created_at": _iso(NOW - timedelta(hours=6)), "due_date": _iso(NOW + timedelta(days=5)), "completed_at": None},
        {"id": _id(), "clinic_id": clinic_id, "patient_id": patients[0]["id"], "title": f"Care gap — {patients[0]['name']}", "description": "Overdue: Rabies booster", "priority": "normal", "status": "open", "source": "auto_alert", "source_id": f"alert_{patients[0]['id']}_Overdue: Rab", "created_at": _iso(NOW - timedelta(hours=12)), "due_date": _iso(NOW + timedelta(days=3)), "completed_at": None},
    ]

    return {
        "owners": owners, "patients": patients, "visits": visits,
        "labs": labs, "weights": weights, "appointments": appointments,
        "messages": messages, "tasks": tasks,
    }
