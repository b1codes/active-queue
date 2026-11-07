// Firestore security rules tests (SPEC §2.2, §4.9).
//
// The client never talks to Firestore: every read and write goes through the API using the
// Admin SDK, which bypasses rules. So the deployed rules must deny ALL client access, and a
// leaked Firebase web config must grant zero data. These tests load the exact rules file
// that firebase.json deploys into the Firestore emulator and try every operation as an
// anonymous caller, as the owner of each document, and as a caller with forged admin
// claims.
//
// Run: make test-firestore-rules (starts the emulator via `firebase emulators:exec`).

import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { after, before, describe, test } from "node:test";
import { fileURLToPath } from "node:url";

import {
  assertFails,
  initializeTestEnvironment,
} from "@firebase/rules-unit-testing";
import {
  collection,
  deleteDoc,
  doc,
  getDoc,
  getDocs,
  query,
  setDoc,
  updateDoc,
  where,
} from "firebase/firestore";

const REPO = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const PROJECT_ID = "demo-activequeue-rules";
const [HOST, PORT] = (process.env.FIRESTORE_EMULATOR_HOST ?? "127.0.0.1:9190").split(":");

const deployedRulesPath = () => {
  const config = JSON.parse(readFileSync(join(REPO, "firebase.json"), "utf8"));
  return join(REPO, config.firestore.rules);
};

const OWNER = "alice";

// One document per collection the backend writes (SPEC §4), plus a collection that
// doesn't exist yet: a default-allow rule added later must not slip through.
const SEEDED = {
  [`users/${OWNER}`]: { uid: OWNER, email: "alice@example.com" },
  [`users/${OWNER}/private/settings`]: { uid: OWNER },
  [`user_authorization/${OWNER}`]: { uid: OWNER, role: "user", disabled: false },
  [`sources/${OWNER}_youtube_PL1`]: { user_id: OWNER, external_source_id: "PL1" },
  [`feed_items/${OWNER}_fx:1`]: { user_id: OWNER, content_id: "fx:1" },
  [`sessions/s_${OWNER}`]: { user_id: OWNER, status: "pending" },
  ["content_cache/fx:1"]: { title: "Shared item" },
  ["activities/running"]: { name: "Running" },
  ["some_future_collection/x"]: { user_id: OWNER },
};

const CALLERS = {
  anonymous: (env) => env.unauthenticatedContext(),
  owner: (env) => env.authenticatedContext(OWNER, { email: "alice@example.com" }),
  "forged admin claims": (env) =>
    env.authenticatedContext(OWNER, { admin: true, role: "admin", firebase: {} }),
};

let env;

before(async () => {
  env = await initializeTestEnvironment({
    projectId: PROJECT_ID,
    firestore: { host: HOST, port: Number(PORT), rules: readFileSync(deployedRulesPath(), "utf8") },
  });
  await env.clearFirestore();
  await env.withSecurityRulesDisabled(async (ctx) => {
    const db = ctx.firestore();
    for (const [path, data] of Object.entries(SEEDED)) {
      await setDoc(doc(db, path), data);
    }
  });
});

after(async () => {
  await env?.clearFirestore();
  await env?.cleanup();
});

describe("deployed rules are the only rules", () => {
  test("firebase.json and firebase.test.json load the same rules file", () => {
    const testConfig = JSON.parse(readFileSync(join(REPO, "firebase.test.json"), "utf8"));
    assert.equal(join(REPO, testConfig.firestore.rules), deployedRulesPath());
  });

  test("no other Firestore rules file exists in the repo (drift guard)", () => {
    const skip = new Set([".git", "node_modules", ".venv", ".terraform", "coverage"]);
    const found = [];
    const walk = (dir) => {
      for (const entry of readdirSync(dir, { withFileTypes: true })) {
        if (skip.has(entry.name)) continue;
        const full = join(dir, entry.name);
        if (entry.isDirectory()) walk(full);
        else if (entry.name.endsWith(".rules")) found.push(relative(REPO, full));
      }
    };
    walk(REPO);
    assert.deepEqual(found, [relative(REPO, deployedRulesPath())]);
  });
});

for (const [caller, contextFor] of Object.entries(CALLERS)) {
  describe(`${caller} caller`, () => {
    for (const path of Object.keys(SEEDED)) {
      test(`cannot read ${path}`, async () => {
        await assertFails(getDoc(doc(contextFor(env).firestore(), path)));
      });

      test(`cannot create, update, or delete ${path}`, async () => {
        const db = contextFor(env).firestore();
        await assertFails(setDoc(doc(db, `${path}-new`), { user_id: OWNER }));
        await assertFails(setDoc(doc(db, path), { user_id: OWNER, hijacked: true }));
        await assertFails(updateDoc(doc(db, path), { hijacked: true }));
        await assertFails(deleteDoc(doc(db, path)));
      });
    }

    for (const name of ["users", "sources", "feed_items", "sessions", "content_cache"]) {
      test(`cannot list or query ${name}`, async () => {
        const db = contextFor(env).firestore();
        await assertFails(getDocs(collection(db, name)));
        await assertFails(getDocs(query(collection(db, name), where("user_id", "==", OWNER))));
      });
    }
  });
}
