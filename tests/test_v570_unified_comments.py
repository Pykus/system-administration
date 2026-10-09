import copy,unittest,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import app
INDEX=(ROOT/"static"/"index.html").read_text(encoding="utf-8")
TEACHER=(ROOT/"static"/"teacher.html").read_text(encoding="utf-8")
APP=(ROOT/"app.py").read_text(encoding="utf-8")

class TestUnifiedComments570(unittest.TestCase):
    def test_version(self):
        self.assertGreaterEqual(tuple(map(int,app.PLANNER_VERSION.split("."))),(5,70))

    def test_comment_metadata_does_not_change_solver_signature(self):
        s=app.ensure_state_schema(copy.deepcopy(app.load_state()))
        a=app._solver_input_signature(s)
        s["preference_comments"]={"Demo":{"Pn|1/2":"powod"}}
        s["manual_block_comments"]={"Demo":{"Pn|1/2":"powod"}}
        self.assertEqual(a,app._solver_input_signature(s))
        s1=copy.deepcopy(s);s2=copy.deepcopy(s)
        lock={"scope":"1-3","abbr":"Pn","slot":"1/2","location":"A","teacher":"Demo","comment":"pierwszy"}
        s1["locked_assignments"]=[lock];s2["locked_assignments"]=[{**lock,"comment":"drugi"}]
        self.assertEqual(app._solver_input_signature(s1),app._solver_input_signature(s2))

    def test_teacher_portal_has_optional_slot_comments(self):
        self.assertIn("prefComments={}",TEACHER)
        self.assertIn('data-comment-k=',TEACHER)
        self.assertIn('placeholder="opcjonalny komentarz / pow&#243;d"',TEACHER)
        self.assertIn("comments:prefComments",TEACHER)
        self.assertIn("data.preference_comments",TEACHER)
        self.assertIn('"preference_comments":st.get("preference_comments"',APP)

    def test_recalc_request_carries_teacher_comment(self):
        self.assertIn('"comment":pref_comment',APP)

    def test_admin_ui_is_unified_and_click_opens_modal(self):
        self.assertGreaterEqual(INDEX.count("Blokady / sta&#322;e przydzia&#322;y dla nauczyciela"),2)
        self.assertIn("@click=\"openAdminConstraintCell('1-3'",INDEX)
        self.assertIn("@click=\"openAdminConstraintCell('school'",INDEX)
        self.assertNotIn('@click="toggleBlock(',INDEX)
        self.assertNotIn('@click="addScopeLock(',INDEX)
        self.assertIn('v-if="adminConstraintModal"',INDEX)

    def test_admin_modal_has_two_choices_and_implicit_day_slot(self):
        start=INDEX.index('v-if="adminConstraintModal"')
        end=INDEX.index('v-if="manualDutyEdit"',start)
        block=INDEX[start:end]
        self.assertIn('<option value="block">Blokada</option>',block)
        self.assertIn('<option value="lock">Sta&#322;y przydzia&#322;</option>',block)
        self.assertEqual(block.count('<option value='),2)
        self.assertIn('v-model="adminConstraintModal.location"',block)
        self.assertIn('v-model="adminConstraintModal.comment"',block)
        self.assertNotIn('v-model="adminConstraintModal.abbr"',block)
        self.assertNotIn('v-model="adminConstraintModal.slot"',block)

    def test_admin_block_comments_are_metadata_only(self):
        self.assertIn('manualBlockComments:{}',INDEX)
        self.assertIn('manual_block_comments:this.manualBlockComments',INDEX)
        self.assertNotIn("manual_block_comments",app._SOLVER_INPUT_STATE_KEYS)
        self.assertNotIn("preference_comments",app._SOLVER_INPUT_STATE_KEYS)

    def test_new_v570_text_has_no_transport_question_marks(self):
        for bad in ("sta?y","przydzia?","blokad?","pow?d","niepo??dana","ustawi?","Nie uda?o","Nieprawid?owe","ust?pstw"):
            self.assertNotIn(bad,INDEX)
            self.assertNotIn(bad,TEACHER)
            self.assertNotIn(bad,APP)

    def test_empty_preference_row_is_functionally_no_change(self):
        s=app.ensure_state_schema(copy.deepcopy(app.load_state()))
        s1=copy.deepcopy(s);s2=copy.deepcopy(s)
        s1.setdefault("preference_grid",{}).pop("Demo",None)
        s2.setdefault("preference_grid",{})["Demo"]={}
        self.assertEqual(app._solver_input_signature(s1),app._solver_input_signature(s2))
        self.assertEqual(app._functional_preference_grid(s1),app._functional_preference_grid(s2))

if __name__=="__main__":
    unittest.main(verbosity=2)
