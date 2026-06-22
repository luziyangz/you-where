import http from "k6/http";
import { check, sleep } from "k6";

const BASE = __ENV.BASE_URL || "http://127.0.0.1:8000/api/v2";
const TOKEN = __ENV.TOKEN || "";
const CATALOG_ID = __ENV.CATALOG_ID || "gutendex_1";

export const options = {
  vus: Number(__ENV.VUS || 10),
  duration: __ENV.DURATION || "30s",
  thresholds: {
    http_req_failed: ["rate<0.02"],
    http_req_duration: ["p(95)<1200"],
  },
};

export default function () {
  if (!TOKEN) throw new Error("需要 TOKEN");
  const headers = { Authorization: `Bearer ${TOKEN}` };
  const list = http.get(`${BASE}/store/books?page=1`, { headers });
  check(list, { "store list": (r) => r.status === 200 });
  const detail = http.get(`${BASE}/store/books/${CATALOG_ID}`, { headers });
  check(detail, { "store detail": (r) => r.status === 200 });
  const read = http.get(`${BASE}/store/books/${CATALOG_ID}/read?page=1`, { headers });
  check(read, { "store read": (r) => r.status === 200 });
  sleep(0.2);
}
