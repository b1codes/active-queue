/**
 * Compile-time half of the API contract (ClickUp 86bcxruxt). Checked by `pnpm typecheck`.
 *
 * `openapi.gen.ts` is generated from contracts/openapi.json (`make contracts`), the same
 * document the backend's provider suite validates real responses against. The aliases
 * below fail to compile when the app's hand-written types drift from it:
 *
 * - Responses: the server's schema must be assignable to the type the app declares, so
 *   every field the app reads exists on the wire with a compatible type (the app may
 *   ignore fields it doesn't use).
 * - Requests: the body the app builds must be assignable to the server's request schema.
 *
 * Runtime behaviour is covered by consumer.test.ts, which replays the recorded examples.
 */
import type { components } from './openapi.gen';
import type { ApiErrorDetail } from '@/core/api/apiClient';
import type {
  Activity,
  ContentMatchResult,
  TimeBlock,
  TimeMatchResult,
} from '@/features/matching/matchingApi';
import type { FeedItem, FeedResponse, Source, SyncChunkResponse } from '@/features/queue/types';
import type {
  CreateSessionInput,
  Session,
  SessionListResponse,
} from '@/features/sessions/sessionApi';

type Schemas = components['schemas'];

/** Resolves to `true` only when A is assignable to B; otherwise the Expect below fails. */
type Assignable<A, B> = [A] extends [B] ? true : false;
type Expect<T extends true> = T;

// Responses: what the server sends -> what the app expects to receive.
export type ResponseContracts = [
  Expect<Assignable<Schemas['ActivitySchema'], Activity>>,
  Expect<Assignable<Schemas['TimeBlockSchema'], TimeBlock>>,
  Expect<Assignable<Schemas['ContentMatchResponse'], ContentMatchResult>>,
  Expect<Assignable<Schemas['TimeMatchResponse'], TimeMatchResult>>,
  Expect<Assignable<Schemas['FeedItemSchema'], FeedItem>>,
  Expect<Assignable<Schemas['FeedResponse'], FeedResponse>>,
  Expect<Assignable<Schemas['SourceSchema'], Source>>,
  Expect<Assignable<Schemas['SyncResponse'], SyncChunkResponse>>,
  Expect<Assignable<Schemas['SessionSchema'], Session>>,
  Expect<Assignable<Schemas['SessionListResponse'], SessionListResponse>>,
  Expect<Assignable<Schemas['ErrorDetail'], ApiErrorDetail>>,
];

// Requests: what the app sends -> what the server accepts.
export type RequestContracts = [
  Expect<Assignable<CreateSessionInput, Schemas['CreateSessionRequest']>>,
  Expect<Assignable<{ url_or_id: string }, Schemas['CreateSourceRequest']>>,
  Expect<Assignable<{ content_id: string }, Schemas['ContentMatchRequest']>>,
  Expect<Assignable<{ target_duration_seconds: number }, Schemas['TimeMatchRequest']>>,
];
