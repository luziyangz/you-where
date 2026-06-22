import http from "k6/http";
import { check, sleep } from "k6";

const BASE = __ENV.BASE_URL || "http://127.0.0.1:8000/api/v2";
const TOKEN_A = __ENV.TOKEN_A || "";
const TOKEN_B = __ENV.TOKEN_B || "";

export const options = {
  vus: Number(__ENV.VUS || 5),
  duration: __ENV.DURATION || "30s",
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<800"],
  },
};

export default function () {
  const token = __VU % 2 === 0 ? TOKEN_A : TOKEN_B;
  if (!token) {
    throw new Error("需要 TOKEN_A 与 TOKEN_B（已绑定 pair 的两个用户）");
  }
  const h = { Authorization: `Bearer ${token}` };
  const cur = http.get(`${BASE}/pairs/current`, { headers: h });
  check(cur, { "pair current 200": (r) => r.status === 200 });
  sleep(0.2);
}
