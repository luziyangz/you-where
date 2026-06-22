import http from "k6/http";
import { check, sleep } from "k6";

const BASE = __ENV.BASE_URL || "http://127.0.0.1:8000/api/v2";

export const options = {
  vus: Number(__ENV.VUS || 10),
  duration: __ENV.DURATION || "30s",
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<800"],
  },
};

export default function () {
  const openId = `k6_u_${__VU}_${__ITER}`;
  const res = http.post(
    `${BASE}/auth/login`,
    JSON.stringify({ code: "test", debug_open_id: openId, nickname: "k6" }),
    { headers: { "Content-Type": "application/json" } }
  );
  check(res, { "login 200": (r) => r.status === 200 });
  if (res.status !== 200) {
    sleep(0.2);
    return;
  }
  const token = JSON.parse(res.body).data.token;
  const me = http.get(`${BASE}/users/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  check(me, { "me 200": (r) => r.status === 200 });
  sleep(0.15);
}
