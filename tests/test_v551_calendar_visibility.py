import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/"static"/"index.html").read_text(encoding="utf-8")

class TestCalendarVisibility551(unittest.TestCase):
    def test_13_calendar_has_separate_display_teacher_list(self):
        self.assertIn("calendarTeachers13()",HTML)
        self.assertIn("this.rows13PlanDisplay",HTML)
        self.assertIn("(t.group==='1-3'&&pool.has(t.name))||assigned.has(t.name)",HTML)
        self.assertIn("let pool=new Set(this.effectiveTeachers13.map(t=>t.name))",HTML)

    def test_13_paging_uses_calendar_not_solver_pool(self):
        self.assertIn("teacherPageCount13(){return Math.max(1,Math.ceil(this.calendarTeachers13.length/this.teacherPageSize))}",HTML)
        self.assertIn("return this.calendarTeachers13.slice(a,a+this.teacherPageSize)",HTML)
        self.assertIn("scope==='13'?this.calendarTeachers13:this.effectiveTeachersSchool",HTML)

    def test_general_teacher_added_to_13_pool_stays_in_school_calendar(self):
        self.assertIn("t.group!=='1-3'||schoolDuty.has(t.name)",HTML)
        self.assertNotIn("let in13=new Set(this.effectiveTeachers13.map(t=>t.name))",HTML)

if __name__=="__main__": unittest.main()
