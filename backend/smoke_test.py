import os
import time

DB_PATH = "/tmp/tunnelconv_smoke.db"
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"

from api import app  # noqa: E402

client = app.test_client()
fails = []


def check(name, cond, detail=""):
    print(("PASS" if cond else "FAIL"), name, detail)
    if not cond:
        fails.append(name)


def login(u, p):
    r = client.post("/api/auth/login", json={"username": u, "password": p})
    assert r.status_code == 200, r.get_data(as_text=True)
    return r.get_json()["access_token"]


def H(tok):
    return {"Authorization": f"Bearer {tok}"}


surv = login("surveyor", "surv123456")
insp = login("inspector", "insp123456")

# --- 当量默认值 ---
r = client.get("/api/equivalent", headers=H(surv))
check("default coefficient 1.0", r.get_json()["coefficient"] == 1.0)

# --- 双路同值：弦长路（系数1.0）与毫米路必须算出同一个数 ---
r1 = client.post("/api/logs", headers=H(surv),
                 json={"chainage": "T1", "chord_mm": 1.2})
check("chord submit 201", r1.status_code == 201, r1.get_data(as_text=True))
id1 = r1.get_json()["id"]
r2 = client.post("/api/logs", headers=H(surv),
                 json={"chainage": "T2", "delta_mm": 1.2})
check("delta submit 201", r2.status_code == 201, r2.get_data(as_text=True))
id2 = r2.get_json()["id"]
check("two paths same delta", r1.get_json()["delta_mm"] == r2.get_json()["delta_mm"] == 1.2)
check("chord path records chord/coeff",
      r1.get_json()["chord_mm"] == 1.2 and r1.get_json()["coefficient"] == 1.0
      and r1.get_json()["input_mode"] == "chord")
check("delta path leaves chord blank",
      r2.get_json()["chord_mm"] is None and r2.get_json()["input_mode"] == "delta")

# 流水与进单同一拍落下：提交返回后立刻可见，且 delta 对得上
led = client.get("/api/ledger", headers=H(surv)).get_json()
l1 = [x for x in led if x["log_id"] == id1][0]
l2 = [x for x in led if x["log_id"] == id2][0]
check("ledger same beat (chord)", l1["delta_mm"] == 1.2 and l1["chord_mm"] == 1.2
      and l1["coefficient"] == 1.0 and l1["input_mode"] == "chord")
check("ledger same beat (delta)", l2["delta_mm"] == 1.2 and l2["chord_mm"] is None)

# --- 维护当量 + 按新当量换算 ---
r = client.put("/api/equivalent", headers=H(surv), json={"coefficient": 0.5})
check("set coeff 0.5", r.status_code == 200 and r.get_json()["coefficient"] == 0.5)
r = client.post("/api/logs", headers=H(surv),
                json={"chainage": "T3", "chord_mm": 4.0})
check("chord 4.0 * 0.5 = 2.0", r.get_json()["delta_mm"] == 2.0, r.get_data(as_text=True))

# 试算接口双路
r = client.post("/api/equivalent/preview", headers=H(surv), json={"chord_mm": 4.0})
check("preview chord", r.status_code == 200 and r.get_json()["delta_mm"] == 2.0)
r = client.post("/api/equivalent/preview", headers=H(surv), json={"delta_mm": -2.3})
check("preview delta passthrough", r.status_code == 200
      and r.get_json()["delta_mm"] == -2.3 and r.get_json()["coefficient"] is None)
r = client.post("/api/equivalent/preview", headers=H(surv),
                json={"chord_mm": 1, "delta_mm": 1})
check("preview both rejected", r.status_code == 400)
r = client.post("/api/equivalent/preview", headers=H(surv), json={})
check("preview neither rejected", r.status_code == 400)

# --- 当量填错或越界退回并说明原因，且旧值不动 ---
for bad, why in [(0, "zero"), (-1, "negative"), (2000, "too big"), ("abc", "not number"), (True, "bool")]:
    r = client.put("/api/equivalent", headers=H(surv), json={"coefficient": bad})
    got = r.get_json().get("detail", "")
    check(f"coeff rejected {why}", r.status_code == 400 and "当量" in got, got)
r = client.get("/api/equivalent", headers=H(surv))
check("coefficient unchanged after rejects", r.get_json()["coefficient"] == 0.5)

# --- 读数越界 / 缺路 / 空桩号 ---
r = client.post("/api/logs", headers=H(surv), json={"chainage": "X", "chord_mm": -0.1})
check("negative chord rejected", r.status_code == 400 and "弦长" in r.get_json()["detail"])
r = client.post("/api/logs", headers=H(surv),
                json={"chainage": "X", "chord_mm": 1, "delta_mm": 1})
check("both paths rejected", r.status_code == 400)
r = client.post("/api/logs", headers=H(surv), json={"chainage": "X"})
check("neither path rejected", r.status_code == 400)
r = client.post("/api/logs", headers=H(surv), json={"chainage": "  ", "delta_mm": 1})
check("blank chainage rejected", r.status_code == 400)
r = client.post("/api/logs", headers=H(surv), json={"chainage": "X", "delta_mm": "abc"})
check("non-numeric rejected", r.status_code == 400)

# --- 巡检员能看流水不能改当量、不能进单 ---
check("inspector reads ledger",
      client.get("/api/ledger", headers=H(insp)).status_code == 200)
check("inspector reads equivalent",
      client.get("/api/equivalent", headers=H(insp)).status_code == 200)
r = client.put("/api/equivalent", headers=H(insp), json={"coefficient": 2})
check("inspector cannot set coeff", r.status_code == 403)
r = client.post("/api/logs", headers=H(insp), json={"chainage": "X", "delta_mm": 1})
check("inspector cannot submit", r.status_code == 403)
r = client.get("/api/logs", headers={"Authorization": "Bearer garbage"})
check("bad token 401", r.status_code == 401)

# --- 判定：按当量应合格的弦长交进去应合格；故意超限的应超限 ---
# 当前系数 0.5：弦长 4.0 -> 2.0 合格；弦长 9.0 -> 4.5 超限
r = client.post("/api/logs", headers=H(surv),
                json={"chainage": "OK1", "chord_mm": 4.0})
ok_id = r.get_json()["id"]
r = client.post("/api/logs", headers=H(surv),
                json={"chainage": "BAD1", "chord_mm": 9.0})
bad_id = r.get_json()["id"]
check("over-limit chord converts 4.5", r.get_json()["delta_mm"] == 4.5)

# 等后台认领线程判完
deadline = time.time() + 8
verdicts = {}
while time.time() < deadline:
    rows = {x["id"]: x for x in client.get("/api/logs", headers=H(surv)).get_json()}
    verdicts = {i: rows.get(i, {}).get("verdict") for i in (id1, id2, ok_id, bad_id)}
    if all(verdicts[i] is not None for i in verdicts):
        break
    time.sleep(0.3)

check("qualified chord -> 合格", verdicts[ok_id] == "合格", str(verdicts))
check("over-limit chord -> 超限", verdicts[bad_id] == "超限", str(verdicts))
check("seed-style 1.2 -> 合格", verdicts[id1] == "合格", str(verdicts))

# 超限记录流水里仍是换算后的 4.5，且与日志一致
led = {x["log_id"]: x for x in client.get("/api/ledger", headers=H(surv)).get_json()}
check("ledger for bad row", led[bad_id]["delta_mm"] == 4.5 and led[bad_id]["chord_mm"] == 9.0)

print()
print("FAILS:", fails if fails else "none")
raise SystemExit(1 if fails else 0)
