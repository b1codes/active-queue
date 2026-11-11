// Creates a fresh Auth-emulator account and exposes its email as output[NAME], so every
// journey signs in as a user nobody else touched. Runs in Maestro's JS engine.
const name = typeof NAME === 'undefined' ? 'user' : NAME;
const email = `e2e-${name}-${Date.now()}@e2e.activequeue.dev`;
const res = http.post(
  `${AUTH_EMULATOR}/identitytoolkit.googleapis.com/v1/accounts:signUp?key=fake-api-key`,
  {
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password: PASSWORD, returnSecureToken: true }),
  },
);
if (res.status !== 200) throw new Error(`signUp ${email} failed: ${res.status} ${res.body}`);
output[name] = email;
