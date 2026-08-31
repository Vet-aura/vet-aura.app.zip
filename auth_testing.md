# Auth Testing Playbook

Auth-Gated App Testing Playbook

## Step 1: Create Test User & Session

```
mongosh --eval "
use('test_database');
var userId = 'test-user-' + Date.now();
var clinicId = 'test-clinic-' + Date.now();
var sessionToken = 'test_session_' + Date.now();
db.clinics.insertOne({
  clinic_id: clinicId,
  name: 'Test Clinic',
  plan: 'trial',
  created_at: new Date()
});
db.users.insertOne({
  user_id: userId,
  clinic_id: clinicId,
  email: 'test.user.' + Date.now() + '@example.com',
  name: 'Test User',
  role: 'owner',
  picture: 'https://via.placeholder.com/150',
  created_at: new Date()
});
db.user_sessions.insertOne({
  user_id: userId,
  session_token: sessionToken,
  expires_at: new Date(Date.now() + 7*24*60*60*1000),
  created_at: new Date()
});
print('Session token: ' + sessionToken);
print('User ID: ' + userId);
print('Clinic ID: ' + clinicId);
"
```

## Step 2: Test Backend API

Every /api/* protected route accepts either:
- `Cookie: session_token=<token>`  (Emergent Google flow)
- `Authorization: Bearer <token>`  (either JWT from email/password OR session_token)

Public endpoints (no auth):
- POST /api/auth/signup — email+password
- POST /api/auth/login — email+password
- POST /api/auth/session — exchange session_id from Google callback
- POST /api/auth/logout
- GET  /api/marketing/pricing — public plan list
- POST /api/marketing/demo — book demo request
- GET  /api/discharge/public/{token} — public owner portal
- POST /api/stripe/webhook

Protected endpoints require auth AND set `request.state.user` + `clinic_id` for scoping.

## Step 3: Browser Testing

Cookie-based (Google flow):
```
context.add_cookies([{
    "name": "session_token",
    "value": token,
    "domain": "your-app.com",
    "path": "/",
    "httpOnly": True,
    "secure": True,
    "sameSite": "None"
}])
```

Token-based (email/password JWT):
```
localStorage.setItem('vetaura_token', token)
axios.defaults.headers.Authorization = 'Bearer ' + token
```

## Test Accounts (see /app/memory/test_credentials.md)
