import http from "k6/http";
import { check, sleep } from "k6";

const BASE = __ENV.BASE_URL || "http://127.0.0.1:8000/api/v2";
const TOKEN = __ENV.TOKEN || "";

export const options = {
  vus: Number(__ENV.VUS || 8),
  duration: __ENV.DURATION || "30s",
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<800"],
  },
};

export default function () {
  if (!TOKEN) throw new Error("需要 TOKEN");
  const headers = {
    Authorization: `Bearer ${TOKEN}`,
    "Content-Type": "application/json",
  };
  const goal = http.get(`${BASE}/users/me/reading-goal`, { headers });
  check(goal, { "goal get": (r) => r.status === 200 });
  const stats = http.get(`${BASE}/users/me/stats`, { headers });
  check(stats, { "stats get": (r) => r.status === 200 });
  const reminder = http.get(`${BASE}/users/me/reminder-config`, { headers });
  check(reminder, { "reminder get": (r) => r.status === 200 });
  sleep(0.2);
}
