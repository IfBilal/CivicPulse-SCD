-- backend/app/providers/ratelimit/lua/fixed_window.lua
-- 09-CACHE-RATELIMIT.md §4.1 — atomic INCR+EXPIRE+TTL in one round trip.
--
-- Why Lua and not INCR + EXPIRE from Python: two round trips are not atomic. If the
-- pod is killed between them, the key has no TTL and that IP is banned forever. Under
-- an HPA that is not hypothetical -- pods are killed on every scale-down. EVALSHA makes
-- this one atomic server-side operation.
--
-- KEYS[1] = rl:{ip}:{window_start}   ARGV[1] = limit   ARGV[2] = window_seconds
local n = redis.call('INCR', KEYS[1])
if n == 1 then redis.call('EXPIRE', KEYS[1], ARGV[2]) end
local ttl = redis.call('TTL', KEYS[1])
return {n, ttl}
