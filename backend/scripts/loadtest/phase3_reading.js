import http from "k6/http";
import { check, sleep } from "k6";

const BASE = __ENV.BASE_URL || "http://127.0.0.1:8000/api/v2";
const TOKEN = __ENV.TOKEN || "";
const BOOK_ID = __ENV.BOOK_ID || "";

export const options = {
  vus: Number(__ENV.VUS || 15),
  duration: __ENV.DURATION || "45s",
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<800"],
  },
};

export default function () {
  if (!TOKEN || !BOOK_ID) {
    throw new Error("需要 TOKEN 与 BOOK_ID");
  }
  const headers = {
    Authorization: `Bearer ${TOKEN}`,
    "Content-Type": "application/json",
  };
  const page = (__ITER % 20) + 1;
  const list = http.get(`${BASE}/books/${BOOK_ID}/entries?page=${page}&page_size=20`, { headers });
  check(list, { "entries list": (r) => r.status === 200 });
  const cid = `k6-${__VU}-${__ITER}-${Date.now()}`;
  const write = http.post(
    `${BASE}/books/${BOOK_ID}/entries`,
    JSON.stringify({ page, note_content: "k6", client_request_id: cid }),
    { headers }
  );
  check(write, { "entry write": (r) => r.status === 200 || r.status === 409 });
  sleep(0.25);
}
