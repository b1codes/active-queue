# Concept Specification: ActiveQueue

**Target Environment:** iOS & Android (Cross-platform)
**Architecture Scope:** Serverless GCP / Mobile Client
**Project Entity:** B1Codes LLC Portfolio

## 1. Executive Summary
ActiveQueue is a mobile application designed to remove friction for individuals who want to stay consistently active while working through their ballooning media watchlist. Instead of tracking traditional metrics (reps, sets, weight), the app acts as a "time-boxing" orchestrator. It matches the exact duration of selected content (podcasts, YouTube videos) to a cardio or timed workout session, ensuring the workout ends precisely as the media finishes. 

## 2. Core Architecture & Tech Stack
* **Frontend:** React Native (optimized for cross-platform speed, deep linking, and HealthKit integration).
* **Backend:** FastAPI deployed via Google Cloud Run (Serverless architecture on GCP).
* **Database:** Firestore (utilizing the local emulator for MVP development and testing).
* **Authentication:** Google Cloud Identity Platform. 
    * *Strict Flow Requirement:* React Native client retrieves JWT -> FastAPI backend verifies token via Firebase Admin SDK for all secure routes. (No frontend-only auth management).
* **Infrastructure Management:** Terraform for reproducible GCP resource provisioning across environments.

## 3. Core Features (MVP)

### A. The "Content-to-Cardio" Matcher
* Integrates with YouTube Data API and Spotify Web API to fetch content duration.
* Users select a specific video or podcast episode, and the app suggests a steady-state workout (e.g., treadmill walking, indoor rowing) of the exact same length.
* Includes simple "Time Blocks" for strength training (e.g., "45-Minute Pull Day Timer") to bypass granular rep tracking.

### B. The Orchestrator Flow (Deep Linking)
To bypass restrictive iframe policies and background-state battery throttling, the app functions as a central launch hub:
1. **Launch Tracker:** Deep links open the user's preferred fitness app (Apple Fitness, Strava, Strong) to begin tracking the physical session.
2. **Launch Media:** Deep links (`vnd.youtube://`, `spotify:episode:`) push the user directly into the native media apps to begin playback.

### C. Session Verification & Completion
* **Manual Loop Closure:** Users return to the app post-workout to hit "Mark Complete."
* **Apple HealthKit Sync (iOS):** Utilizes `react-native-health` to query recent workouts. Automatically matches the duration of the finished content to a recently logged HealthKit workout, storing the HealthKit UUID as verification.
* **External URL Linking:** Users tracking via external platforms (like Strava) can paste their completed workout web link directly into the session record.

### D. Content Feed Management
* **Auto-Hide:** Upon session completion, the content's unique ID is pushed to a `consumed_content_ids` array to prevent future recommendations of the same episode/video.
* **Manual Hide:** A swipe-to-complete gesture allows users to mark media they consumed outside of a workout as "watched/listened" to clear the queue.

### E. Gym & Park Finder
* Integrates with the Google Places API to locate nearby parks and fitness centers.
* Users can save locations to a favorites list, saving the Google Place ID to dynamically fetch open hours without needing to store or update changing operating times.

## 4. Initial Database Schema (Firestore)

**`users` (Collection)**
* `uid` (String) - Mapped from GC Identity Platform
* `preferences` (Map) - Preferred cardio types, preferred tracker app, media platform preferences
* `saved_locations` (Array of Strings) - Google Place IDs
* `consumed_content_ids` (Array of Strings) - YouTube Video IDs / Spotify URIs

**`sessions` (Collection)**
* `user_id` (String)
* `content_id` (String)
* `content_duration_seconds` (Integer)
* `activity_type` (String)
* `completed_at` (Timestamp, Nullable)
* `external_workout_url` (String, Nullable) - For Strava/Strong deep links
* `healthkit_uuid` (String, Nullable) - For Apple Health auto-verification

