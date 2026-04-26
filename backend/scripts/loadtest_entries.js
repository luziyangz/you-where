import http from "k6/http";
import { check, sleep } from "k6";

const BASE_URL = __ENV.BASE_URL || "http://127.0.0.1:8000/api/v2";
const BOOK_ID = __ENV.BOOK_ID || "";
const TOKEN = __ENV.TOKEN || "";
const PAGE_SIZE = Number(__ENV.PAGE_SIZE || 30);

if (!BOOK_ID || !TOKEN) {
  throw new Error("Please provide BOOK_ID and TOKEN environment variables.");
}

const headers = {
  Authorization: `Bearer ${TOKEN}`,
  "Content-Type": "application/json",
};

export const options = {
  scenarios: {
    entries_read_flow: {
      executor: "ramping-vus",
      startVUs: 5,
      stages: [
        { duration: "30s", target: 20 },
        { duration: "1m", target: 50 },
        { duration: "30s", target: 0 },
      ],
      exec: "readEntries",
    },
    entries_write_flow: {
      executor: "ramping-vus",
      startVUs: 1,
      stages: [
        { duration: "20s", target: 10 },
        { duration: "40s", target: 30 },
        { duration: "20s", target: 0 },
      ],
      exec: "writeEntries",
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<800"],
  },
};

export function readEntries() {
  const page = Math.floor(Math.random() * 5) + 1;
  const url = `${BASE_URL}/books/${BOOK_ID}/entries?page=${page}&page_size=${PAGE_SIZE}`;
  const res = http.get(url, { headers });

  check(res, {
    "read status is 200": (r) => r.status === 200,
    "pagination exists": (r) => {
      try {
        const body = JSON.parse(r.body);
        return !!(body.data && body.data.pagination);
      } catch (error) {
        return false;
      }
    },
  });
  sleep(0.2);
}

export function writeEntries() {
  const page = Math.floor(Math.random() * 200) + 1;
  const clientRequestId = `k6-${__VU}-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`;
  const payload = JSON.stringify({
    page,
    note_content: "k6 load test note",
    client_request_id: clientRequestId,
  });
  const res = http.post(`${BASE_URL}/books/${BOOK_ID}/entries`, payload, { headers });

  check(res, {
    "write status is 200 or 409": (r) => r.status === 200 || r.status === 409,
  });
  sleep(0.3);
}
