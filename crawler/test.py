import json, glob
from collections import Counter
cm = json.load(open("crawler/mapping/chuyen_mon_mapping.json", encoding="utf-8"))
ket_qua, chua_map = Counter(), Counter()
for p in glob.glob("crawler/raw_data/jobs/*.json"):
    ds = json.load(open(p, encoding="utf-8")).get("job_expertise") or []
    chua_map.update(e for e in ds if e not in cm)   # tag chưa có trong mapping
    ket_qua[next((cm[e] for e in ds if cm.get(e) and cm[e] != "Khác"), "Khác")] += 1
print(ket_qua.most_common())
print("Chưa map:", chua_map.most_common())