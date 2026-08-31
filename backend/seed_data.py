"""Seed realistic veterinary demo data on server startup."""
from datetime import datetime, timezone, timedelta
import uuid

def _id():
    return str(uuid.uuid4())

def _iso(dt):
    return dt.isoformat()

NOW = datetime.now(timezone.utc)


def build_seed():
    owners = [
        {"id": _id(), "name": "Amelia Fischer", "email": "amelia.f@example.com", "phone": "(415) 555-0142", "language": "English"},
        {"id": _id(), "name": "Marcus Chen", "email": "marcus.c@example.com", "phone": "(415) 555-0178", "language": "English"},
        {"id": _id(), "name": "Sofia Ruiz", "email": "sofia.r@example.com", "phone": "(415) 555-0193", "language": "Spanish"},
        {"id": _id(), "name": "Priya Nair", "email": "priya.n@example.com", "phone": "(415) 555-0211", "language": "English"},
    ]

    patients = [
        {"id": _id(), "name": "Bella", "species": "Canine", "breed": "Golden Retriever", "age_years": 7, "sex": "Spayed Female", "weight_kg": 32.4, "microchip": "985141005512334", "owner_id": owners[0]["id"], "active_problems": ["Atopic dermatitis", "Otitis externa (chronic)"], "alerts": ["Overdue: Rabies booster"]},
        {"id": _id(), "name": "Milo", "species": "Feline", "breed": "Domestic Shorthair", "age_years": 12, "sex": "Neutered Male", "weight_kg": 4.1, "microchip": "985141005519087", "owner_id": owners[1]["id"], "active_problems": ["Chronic kidney disease (IRIS Stage 2)"], "alerts": ["Elevated SDMA — trend up"]},
        {"id": _id(), "name": "Luna", "species": "Canine", "breed": "French Bulldog", "age_years": 3, "sex": "Intact Female", "weight_kg": 11.8, "microchip": "985141005520114", "owner_id": owners[2]["id"], "active_problems": ["Grade 2 medial patellar luxation (L)"], "alerts": []},
        {"id": _id(), "name": "Ollie", "species": "Canine", "breed": "Labrador Retriever", "age_years": 5, "sex": "Neutered Male", "weight_kg": 34.7, "microchip": "985141005525999", "owner_id": owners[3]["id"], "active_problems": ["Post-op TPLO (R stifle) — Day 10"], "alerts": ["Recheck due in 4 days"]},
    ]

    visits = [
        {"id": _id(), "patient_id": patients[0]["id"], "date": _iso(NOW - timedelta(days=45)), "reason": "Recheck otitis externa", "type": "Dermatology", "signed": True, "vet": "Dr. Reyes"},
        {"id": _id(), "patient_id": patients[0]["id"], "date": _iso(NOW - timedelta(days=180)), "reason": "Annual wellness", "type": "Wellness", "signed": True, "vet": "Dr. Reyes"},
        {"id": _id(), "patient_id": patients[1]["id"], "date": _iso(NOW - timedelta(days=30)), "reason": "CKD monitoring bloodwork", "type": "Internal medicine", "signed": True, "vet": "Dr. Okafor"},
        {"id": _id(), "patient_id": patients[1]["id"], "date": _iso(NOW - timedelta(days=120)), "reason": "Weight loss workup", "type": "Internal medicine", "signed": True, "vet": "Dr. Okafor"},
        {"id": _id(), "patient_id": patients[2]["id"], "date": _iso(NOW - timedelta(days=10)), "reason": "Intermittent left hind lameness", "type": "Orthopedics", "signed": True, "vet": "Dr. Reyes"},
        {"id": _id(), "patient_id": patients[3]["id"], "date": _iso(NOW - timedelta(days=10)), "reason": "TPLO surgery — R stifle", "type": "Surgery", "signed": True, "vet": "Dr. Okafor"},
    ]

    labs = [
        # Milo CKD trend
        {"id": _id(), "patient_id": patients[1]["id"], "date": _iso(NOW - timedelta(days=180)), "creatinine": 1.6, "bun": 28, "sdma": 14, "phosphorus": 4.2, "usg": 1.028},
        {"id": _id(), "patient_id": patients[1]["id"], "date": _iso(NOW - timedelta(days=120)), "creatinine": 1.9, "bun": 32, "sdma": 16, "phosphorus": 4.6, "usg": 1.021},
        {"id": _id(), "patient_id": patients[1]["id"], "date": _iso(NOW - timedelta(days=60)), "creatinine": 2.2, "bun": 38, "sdma": 19, "phosphorus": 5.1, "usg": 1.017},
        {"id": _id(), "patient_id": patients[1]["id"], "date": _iso(NOW - timedelta(days=30)), "creatinine": 2.5, "bun": 42, "sdma": 22, "phosphorus": 5.4, "usg": 1.015},
    ]

    weights = [
        {"id": _id(), "patient_id": patients[0]["id"], "date": _iso(NOW - timedelta(days=365)), "weight_kg": 30.1},
        {"id": _id(), "patient_id": patients[0]["id"], "date": _iso(NOW - timedelta(days=180)), "weight_kg": 31.2},
        {"id": _id(), "patient_id": patients[0]["id"], "date": _iso(NOW - timedelta(days=45)), "weight_kg": 32.0},
        {"id": _id(), "patient_id": patients[0]["id"], "date": _iso(NOW), "weight_kg": 32.4},
        {"id": _id(), "patient_id": patients[1]["id"], "date": _iso(NOW - timedelta(days=365)), "weight_kg": 5.2},
        {"id": _id(), "patient_id": patients[1]["id"], "date": _iso(NOW - timedelta(days=180)), "weight_kg": 4.8},
        {"id": _id(), "patient_id": patients[1]["id"], "date": _iso(NOW - timedelta(days=60)), "weight_kg": 4.3},
        {"id": _id(), "patient_id": patients[1]["id"], "date": _iso(NOW - timedelta(days=30)), "weight_kg": 4.1},
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
            "id": _id(),
            "patient_id": pat["id"],
            "datetime": _iso(dt),
            "reason": reason,
            "type": apt_type,
            "vet": vet,
            "room": room,
            "status": "scheduled",
        })

    messages = [
        {"id": _id(), "owner_id": owners[0]["id"], "patient_id": patients[0]["id"], "received_at": _iso(NOW - timedelta(hours=2)), "channel": "Portal", "subject": "Bella scratching her ears again", "body": "Hi, Bella has been shaking her head and scratching her right ear a lot since yesterday. She finished the last course of drops two weeks ago. Should I bring her in?", "status": "new", "draft": None},
        {"id": _id(), "owner_id": owners[3]["id"], "patient_id": patients[3]["id"], "received_at": _iso(NOW - timedelta(hours=5)), "channel": "SMS", "subject": "Ollie licking incision", "body": "Ollie keeps trying to lick his TPLO incision even with the cone on. It looks slightly pink around the edges but no discharge. Is this normal at day 10?", "status": "new", "draft": None},
        {"id": _id(), "owner_id": owners[1]["id"], "patient_id": patients[1]["id"], "received_at": _iso(NOW - timedelta(hours=8)), "channel": "Email", "subject": "Refill request — benazepril", "body": "Hello, we're almost out of Milo's benazepril (2.5mg once daily). Could you refill it? Thanks!", "status": "new", "draft": None},
        {"id": _id(), "owner_id": owners[2]["id"], "patient_id": patients[2]["id"], "received_at": _iso(NOW - timedelta(days=1)), "channel": "Portal", "subject": "Luna's limp", "body": "Luna's limp comes and goes. She was running at the park yesterday and then held her leg up for about a minute. She seems fine now. What should we do?", "status": "new", "draft": None},
    ]

    return {
        "owners": owners,
        "patients": patients,
        "visits": visits,
        "labs": labs,
        "weights": weights,
        "appointments": appointments,
        "messages": messages,
    }
