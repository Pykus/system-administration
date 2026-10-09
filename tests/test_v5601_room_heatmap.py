import unittest
from pathlib import Path
import app

ROOT=Path(__file__).resolve().parents[1]

class RoomHeatmapTests(unittest.TestCase):
    def test_api_uses_unique_weekly_slots(self):
        data=app.map_lessons()
        self.assertEqual(data["total_slots"],45)
        self.assertEqual(data["days"],["Pn","Wt","Śr","Czw","Pi"])
        self.assertEqual(data["periods"],list(range(1,10)))
        self.assertIn("123",data["rooms"])
        room=data["rooms"]["123"]
        self.assertLessEqual(room["occupied_slots"],45)
        self.assertEqual(room["occupied_slots"]+room["free_slots"],45)
        expected=set()
        for t in app.SEED.get("teachers",[]):
            for day,rows in (t.get("lessons") or {}).items():
                for period,vals in (rows or {}).items():
                    vals=vals if isinstance(vals,list) else [vals]
                    if any(str((x or {}).get("room") or "").strip()=="123" for x in vals):
                        expected.add((day,int(period)))
        self.assertEqual(room["occupied_slots"],len(expected))

    def test_map_is_lesson_heatmap_not_computer_map(self):
        html=(ROOT/"static"/"map.html").read_text(encoding="utf-8")
        low=html.casefold()
        self.assertNotIn("komputer",low)
        self.assertNotIn("roomdevices",low)
        self.assertNotIn("data.devices",low)
        self.assertIn("/api/map/lessons",html)
        self.assertIn("heatColor",html)
        self.assertIn("roomSchedule",html)
        self.assertIn("freeSlot",html)
        self.assertIn("mniej lekcji",html)
        self.assertIn("więcej lekcji",html)

    def test_key_rooms_remain_in_geometry(self):
        html=(ROOT/"static"/"map.html").read_text(encoding="utf-8")
        for room in ('"13"','"123"','"218"','"220"','"233"'):
            self.assertIn(room,html)

if __name__=="__main__":
    unittest.main(verbosity=2)
