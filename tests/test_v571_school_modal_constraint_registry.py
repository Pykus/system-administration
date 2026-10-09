import unittest,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import app
HTML=(ROOT/"static"/"index.html").read_text(encoding="utf-8")

class TestV571(unittest.TestCase):
    def test_version(self):
        self.assertGreaterEqual(tuple(map(int,app.PLANNER_VERSION.split("."))),(5,71))

    def test_school_matrix_wires_cell_action(self):
        marker=':mode="displayModeSchool" @cell-action="openDutyCellAction"'
        self.assertIn(marker,HTML)

    def test_both_unified_panels_have_all_teacher_registry(self):
        self.assertEqual(HTML.count("Aktywne blokady i sta&#322;e przydzia&#322;y &mdash; wszyscy nauczyciele"),2)
        self.assertIn("allAdminConstraints('1-3')",HTML)
        self.assertIn("allAdminConstraints('school')",HTML)
        for col in ("Nauczyciel","Dzie&#324;","Slot","Typ","Miejsce","Komentarz / pow&#243;d"):
            self.assertIn(col,HTML)

    def test_registry_contains_manual_blocks_and_fixed_assignments(self):
        self.assertIn("Object.entries(this.manualBlocks||{})",HTML)
        self.assertIn("this.lockedAssignments||[]",HTML)
        self.assertIn("manualBlockComments",HTML)

    def test_registry_rows_can_edit_and_remove(self):
        self.assertIn("@click=\"editAdminConstraintRow(r)\"",HTML)
        self.assertIn("@click=\"removeAdminConstraintRow(r)\"",HTML)
        self.assertIn("editAdminConstraintRow(r){",HTML)
        self.assertIn("removeAdminConstraintRow(r){",HTML)

    def test_school_scope_accepts_legacy_scope_names(self):
        self.assertIn("sameAdminScope(a,b)",HTML)
        self.assertIn("this.sameAdminScope(x.scope,scope)",HTML)

    def test_manual_block_survives_schema_and_is_available_to_registry(self):
        s=app.ensure_state_schema({"manual_blocks":{"Marta Lewandowska":["Pn|7/8"]}})
        self.assertIn("Pn|7/8",(s.get("manual_blocks") or {}).get("Marta Lewandowska",[]))

    def test_new_registry_text_has_no_transport_damage(self):
        for bad in ("Sta?y","przydzia?","przydzia&#322;?w"," ? wszyscy nauczyciele"):
            self.assertNotIn(bad,HTML)
        self.assertIn("Sta\\u0142y przydzia\\u0142",HTML)
        self.assertIn("przydzia&#322;&#243;w",HTML)

if __name__=="__main__":
    unittest.main(verbosity=2)
