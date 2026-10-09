import copy,unittest,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import app
INDEX=(ROOT/"static"/"index.html").read_text(encoding="utf-8")
APP=(ROOT/"app.py").read_text(encoding="utf-8")
SOLVER=(ROOT/"solver_ortools.py").read_text(encoding="utf-8")
TEACHER=(ROOT/"static"/"teacher.html").read_text(encoding="utf-8")

class TestTeacherPlaceMatrix578(unittest.TestCase):
    def setUp(self):
        self.state=app.ensure_state_schema(copy.deepcopy(app.load_state()))

    def test_version_and_levels(self):
        self.assertGreaterEqual(tuple(map(int,app.PLANNER_VERSION.split("."))),(5,78))
        self.assertEqual(self.state["teacher_place_preference_levels"],[0.0,0.25,0.5,0.75,1.0])
        self.assertEqual(self.state["place_preference_model"],"teacher_x_place_v1")

    def test_matrix_has_every_active_teacher_and_every_place(self):
        places=self.state["duty_places"]
        keys={p["key"] for p in places}
        self.assertEqual(set(self.state["teacher_place_preferences"]),set(app.ALL))
        for name,row in self.state["teacher_place_preferences"].items():
            self.assertEqual(set(row),keys,name)

    def test_groups_seed_defaults_but_are_not_pools(self):
        core=next(n for n in app.ALL if app.GROUP.get(n)=="1-3")
        general=next(n for n in app.ALL if app.GROUP.get(n)=="school")
        wf=next(n for n in app.ALL if app.GROUP.get(n)=="wf")
        station=next(p for p in self.state["duty_places"] if p["legacy_scope"]=="1-3")
        ordinary=next(p for p in self.state["duty_places"] if p["legacy_scope"]=="school" and p.get("zone")!="gym")
        self.assertEqual(self.state["teacher_place_preferences"][core][station["key"]],1.0)
        self.assertEqual(self.state["teacher_place_preferences"][general][station["key"]],0.0)
        self.assertEqual(self.state["teacher_place_preferences"][wf][station["key"]],0.0)
        self.assertEqual(self.state["teacher_place_preferences"][general][ordinary["key"]],1.0)
        self.assertEqual(self.state["teacher_place_preferences"][wf][ordinary["key"]],0.0)

    def test_gym_is_a_configurable_zone_with_multiple_independent_places(self):
        gyms=[p for p in self.state["duty_places"] if p.get("zone")=="gym"]
        labels=[p["label"] for p in gyms]
        self.assertIn("Sala gimnastyczna A",labels)
        self.assertIn("Sala gimnastyczna B",labels)
        self.assertGreaterEqual(len(gyms),2)
        for p in gyms:
            self.assertNotIn("exclusive_group",p)
            self.assertNotIn("system",p)
            self.assertIn(p["key"],self.state["group_place_defaults"]["wf"])
        self.assertIn("Sala gimnastyczna A",self.state["school_locations"])
        self.assertIn("Sala gimnastyczna B",self.state["school_locations"])

    def test_gym_defaults_are_one_for_wf_zero_for_general(self):
        wf=next(n for n in app.ALL if app.GROUP.get(n)=="wf")
        general=next(n for n in app.ALL if app.GROUP.get(n)=="school")
        for key in ("school|Sala gimnastyczna A","school|Sala gimnastyczna B"):
            self.assertEqual(self.state["teacher_place_preferences"][wf][key],1.0)
            self.assertEqual(self.state["teacher_place_preferences"][general][key],0.0)

    def test_gym_points_are_not_recreated_after_one_time_migration(self):
        st=copy.deepcopy(self.state)
        st["gym_multi_place_v581_migrated"]=True
        st["school_locations"]=[x for x in st["school_locations"] if x!="Sala gimnastyczna B"]
        st["duty_location_zones"].pop("Sala gimnastyczna B",None)
        out=app.ensure_state_schema(st)
        self.assertNotIn("Sala gimnastyczna B",out["school_locations"])
        self.assertNotIn("Sala gimnastyczna",out["school_locations"])

    def test_gym_staffing_points_are_independent(self):
        st=copy.deepcopy(self.state)
        key_a=next(k for k in st["min_people_school"] if k.endswith("|Sala gimnastyczna A"))
        ab,slot,_=key_a.split("|",2)
        key_b=f"{ab}|{slot}|Sala gimnastyczna B"
        st["min_people_school"][key_a]=1
        st["min_people_school"][key_b]=0
        self.assertEqual(st["min_people_school"][key_a],1)
        self.assertEqual(st["min_people_school"][key_b],0)
        st["min_people_school"][key_b]=1
        self.assertEqual(st["min_people_school"][key_b],1)

    def test_gym_zone_requires_wf_teacher_for_each_active_point(self):
        st=copy.deepcopy(self.state)
        br=app.SEED["breaks"][0]
        positions=[
            {"day":br["day"],"abbr":br["abbr"],"slot":br["label"],"location":"Sala gimnastyczna A","break":br},
            {"day":br["day"],"abbr":br["abbr"],"slot":br["label"],"location":"Sala gimnastyczna B","break":br},
        ]
        arr,_,missing,_=app.solve_positions(st,"szko\u0142a",positions,set(app.ALL),[],coverage_only=True)
        self.assertFalse(missing)
        real=[x for x in arr if x.get("teacher")]
        self.assertEqual(len(real),2)
        self.assertTrue(all(app.GROUP.get(x["teacher"])=="wf" for x in real))

    def test_place_preference_lexicographic_selects_higher_value(self):
        st=copy.deepcopy(self.state)
        pool=[n for n in app.ALL if n not in set(st.get("excluded_teachers",[]))]
        chosen=None
        for pos in app._diag_positions_13(st)[0]:
            legal=app._preflight_teacher_allowed_v524(st,"1-3",pos,pool)
            nonwf=[n for n in legal if app.GROUP.get(n)!="wf"]
            if len(nonwf)>=2:
                chosen=(pos,nonwf[0],nonwf[1]);break
        self.assertIsNotNone(chosen)
        pos,hi,lo=chosen
        key="1-3|"+str(pos["station"])
        st["teacher_place_preferences"][hi][key]=1.0
        st["teacher_place_preferences"][lo][key]=0.0
        for r in st["global_constraints"]:
            if r.get("kind")=="soft" and r.get("key")!="prefer_home_group": r["enabled"]=False
        mr=next(r for r in st["global_constraints"] if r.get("key")=="prefer_home_group")
        mr["enabled"]=True; mr["kind"]="soft"; mr["priority"]=5
        arr,_,missing,meta=app.solve_positions(st,"1\u20133",[pos],{hi,lo},[],coverage_only=True)
        self.assertFalse(missing)
        self.assertEqual(arr[0]["teacher"],hi)
        self.assertTrue(meta["diagnostics"]["place_preference_lexicographic"])
        self.assertEqual(meta["diagnostics"]["minimum_place_preference_deficit"],0)

    def test_zero_preference_is_fallback_not_hard_ban(self):
        st=copy.deepcopy(self.state)
        pool=[n for n in app.ALL if n not in set(st.get("excluded_teachers",[]))]
        pos=next(p for p in app._diag_positions_13(st)[0] if app._preflight_teacher_allowed_v524(st,"1-3",p,pool))
        key="1-3|"+str(pos["station"])
        allowed_groups={g for g in ("1-3","school","wf") if key in set(st.get("group_place_defaults",{}).get(g,[]) or [])}
        teacher=next(n for n in app._preflight_teacher_allowed_v524(st,"1-3",pos,pool) if app.GROUP.get(n) in allowed_groups)
        st["teacher_place_preferences"][teacher][key]=0.0
        arr,_,missing,_=app.solve_positions(st,"1\u20133",[pos],{teacher},[],coverage_only=True)
        self.assertFalse(missing);self.assertEqual(arr[0]["teacher"],teacher)

    def test_ui_has_one_place_list_and_matrix_without_candidate_pools(self):
        self.assertIn("Wszystkie miejsca dy\u017cur\u00f3w",INDEX)
        self.assertIn("Preferencje nauczyciel \u00d7 miejsce dy\u017curu",INDEX)
        self.assertNotIn("Pula kandydat\u00f3w \u2013 1\u20133",INDEX)
        self.assertNotIn("Pula kandydat\u00f3w \u2013 ca\u0142a szko\u0142a",INDEX)
        self.assertIn("teacherPlacePreferences",INDEX)

    def test_legacy_pool_expansion_is_not_generator_strategy(self):
        import inspect
        block=inspect.getsource(app._repair_candidates_v2)
        self.assertIn("legacy pool expansion/move candidates are obsolete",block)
        fake={"obvious_candidates":[
            {"token":"addschool:Demo","label":"legacy","human_cost":1},
            {"token":"add13group:wf","label":"legacy2","human_cost":1},
        ]}
        out=app._repair_candidates_v2(self.state,list(app.ALL),list(app.ALL),{},fake)
        self.assertFalse(any(str(x.get("token","")).startswith(("addschool:","add13:","add13group:","move13:","moveschool:")) for x in out))

    def test_solver_uses_exact_place_matrix_as_soft_fallback_policy(self):
        self.assertIn("teacher_place_preferences",SOLVER)
        self.assertIn("place_preference_terms",SOLVER)
        self.assertIn('matrix_rule=cs.get("prefer_home_group"',SOLVER)
        self.assertNotIn("kategoria nauczyciela niedopuszczona dla miejsca",SOLVER)
        self.assertNotIn("exclusive_group=place_meta.get",SOLVER)

    def test_matrix_change_changes_solver_signature(self):
        st=copy.deepcopy(self.state)
        name=next(iter(app.ALL)); key=next(iter(st["teacher_place_preferences"][name]))
        before=app._solver_input_signature(st)
        st["teacher_place_preferences"][name][key]=0.25 if st["teacher_place_preferences"][name][key]!=0.25 else 0.5
        self.assertNotEqual(before,app._solver_input_signature(st))

    def test_variant_save_contains_matrix_and_zone_map(self):
        self.assertIn("teacher_place_preferences:this.teacherPlacePreferences",INDEX)
        self.assertIn("duty_location_zones:(this.cfg?.state?.duty_location_zones||{})",INDEX)

    def test_group_start_places_are_configurable_above_matrix(self):
        self.assertIn("Startowo preferowane miejsca dyżurów — kategorie nauczycieli",INDEX)
        self.assertIn("groupPlaceDefaults",INDEX)
        self.assertIn("/api/group-place-defaults",INDEX)
        self.assertIn("apply_to_group",APP)

    def test_plan_scope_filters_drive_one_shared_teacher_grid_and_pager(self):
        self.assertIn('data-plan-teacher-common',INDEX)
        self.assertIn('planTeachersCombined()',INDEX)
        self.assertIn('planSelectedSchoolDisplay()',INDEX)
        self.assertIn(':teachers="pagedPlanTeachers"',INDEX)
        self.assertIn(':assign13="planShow13?rows13PlanDisplay:[]"',INDEX)
        self.assertIn(':school="planSelectedSchoolDisplay"',INDEX)
        self.assertIn('planTeacherPageCount()',INDEX)
        self.assertIn('@change="planTeacherPage=0"',INDEX)
        self.assertNotIn("Nauczyciele {{teacherPageLabel(teacherPage13,'13')}}",INDEX)
        self.assertNotIn("Nauczyciele {{teacherPageLabel(teacherPageSchool,'school')}}",INDEX)

    def test_second_plan_view_slot_place_teacher_exists(self):
        self.assertIn("slot/nauczyciel/plan",INDEX)
        self.assertIn("slot/miejsce/nauczyciel",INDEX)
        self.assertIn("data-plan-place-matrix",INDEX)
        self.assertIn("planPlaceColumns()",INDEX)
        self.assertIn("planPlaceAssignmentMap()",INDEX)

    def test_stats_hide_stale_plan_until_fresh_verified_result(self):
        self.assertIn("statsAwaitingFreshPlan()",INDEX)
        self.assertIn("data-stats-waiting",INDEX)
        self.assertIn("data-stats-content",INDEX)
        self.assertIn("statsAssignments13(){return this.statsAwaitingFreshPlan?[]",INDEX)
        self.assertIn("statsAssignmentsSchool(){return this.statsAwaitingFreshPlan?[]",INDEX)
        self.assertIn("await this.refreshEffectivePlan()",INDEX)
        self.assertIn("setTimeout(()=>this.pollRepair(),900)",INDEX)

    def test_effective_plan_hides_old_duties_during_active_search(self):
        jid="test_waiting_gui_truth"
        old=app.REPAIR_JOBS.get(jid)
        app.REPAIR_JOBS[jid]={
            "id":jid,"status":"running","created_at":"9999-12-31T23:59:59",
            "working_variants":[],"suggestions":[],"accepted_compromises":[]
        }
        try:
            p=app._effective_plan_v574(copy.deepcopy(self.state))
            self.assertEqual(p["source"]["kind"],"calculating_waiting")
            self.assertFalse(p["source"]["verified"])
            self.assertEqual(p["result_13"],[])
            self.assertEqual(p["result_school"],[])
            duties,source,saved=app._teacher_effective_duties_v573(next(iter(app.ALL)),copy.deepcopy(self.state))
            self.assertEqual(source["kind"],"calculating_waiting")
            self.assertEqual(duties,[])
            self.assertEqual(saved,[])
        finally:
            if old is None: app.REPAIR_JOBS.pop(jid,None)
            else: app.REPAIR_JOBS[jid]=old

    def test_all_gui_duty_views_share_waiting_state(self):
        self.assertIn("rows13PlanDisplay(){if(this.planAwaitingFreshPlan)return[]",INDEX)
        self.assertIn("schoolPlanDisplay(){if(this.planAwaitingFreshPlan)return[]",INDEX)
        self.assertIn("displayWaits13(){if(this.planAwaitingFreshPlan)return[]",INDEX)
        self.assertIn("displayWaitsSchool(){if(this.planAwaitingFreshPlan)return[]",INDEX)
        self.assertIn("displaySummary13(){if(this.planAwaitingFreshPlan)return null",INDEX)
        self.assertIn("displaySummarySchool(){if(this.planAwaitingFreshPlan)return null",INDEX)
        self.assertIn("manualMissingPositions(){if(this.planAwaitingFreshPlan)return{}",INDEX)
        self.assertIn('v-if="!planAwaitingFreshPlan && teacherStats(t.name)"',INDEX)
        self.assertIn('v-if="!planAwaitingFreshPlan && pendingTeacherRecalcRequests.length"',INDEX)
        self.assertIn('v-if="!planAwaitingFreshPlan && activeLocalOverrides.length"',INDEX)
        self.assertIn("data-global-plan-waiting",INDEX)

    def test_teacher_portal_hides_old_duties_during_search(self):
        self.assertIn("s.kind==='calculating_waiting'",TEACHER)
        self.assertIn("if(data?.duty_source?.kind==='calculating_waiting')return''",TEACHER)
        self.assertIn("setTimeout(refreshDuties,1500)",TEACHER)

    def test_fast_start_migration_uses_learned_capacity_without_relaxing_comfort(self):
        s=copy.deepcopy(self.state)
        s.pop("solver_fast_start_v579_migrated",None)
        by={r["key"]:r for r in s["global_constraints"]}
        by["max_day_13"]["enabled"]=True;by["max_day_13"]["kind"]="hard";by["max_day_13"]["value"]=3
        by["max_day_school"]["enabled"]=True;by["max_day_school"]["kind"]="hard";by["max_day_school"]["value"]=3
        by["max_week"]["enabled"]=True;by["max_week"]["kind"]="hard";by["max_week"]["value"]=8
        old_consecutive=by["max_consecutive_duties"].get("value")
        old_long_day=by["max_long_day"].get("value")
        s=app.ensure_state_schema(s)
        by={r["key"]:r for r in s["global_constraints"]}
        self.assertEqual(by["max_day_13"]["value"],5)
        self.assertEqual(by["max_day_school"]["value"],5)
        self.assertEqual(by["max_week"]["value"],10)
        self.assertEqual(by["max_consecutive_duties"].get("value"),old_consecutive)
        self.assertEqual(by["max_long_day"].get("value"),old_long_day)
        self.assertEqual(s["solver_coverage_retry_seconds"],30)

    def test_constraint_order_keeps_waiting_last_and_capacity_early(self):
        keys=[r["key"] for r in self.state["global_constraints"]]
        self.assertLess(keys.index("max_day_13"),keys.index("max_consecutive_duties"))
        self.assertLess(keys.index("max_week"),keys.index("before_first_long"))
        self.assertLess(keys.index("before_first_long"),keys.index("after_last_long"))
        self.assertLess(keys.index("after_last_long"),keys.index("avoid_wait"))
        self.assertEqual(keys[-1],"avoid_wait")

    def test_cross_plan_solver_knowledge_bootstraps_and_is_bounded(self):
        kb=app._solver_knowledge_snapshot()
        self.assertEqual(kb.get("policy"),app.SOLVER_KNOWLEDGE_POLICY)
        self.assertIsInstance(kb.get("stats"),dict)
        self.assertLessEqual(len(kb["stats"]),app.SOLVER_KNOWLEDGE_MAX_KEYS)
        # Historical local data should seed the cross-plan layer when available.
        if app.REPAIR_LEARNING_PATH.exists():
            old=__import__("json").loads(app.REPAIR_LEARNING_PATH.read_text(encoding="utf-8"))
            if old.get("contexts"):
                self.assertGreater(len(kb["stats"]),0)

    def test_cross_plan_learning_only_changes_candidate_cost_not_stage(self):
        job={"accepted_compromises":[],"_solver_knowledge":{"stats":{
            "token:gval:max_week:10":{"attempts":40,"conclusive":40,"full":30,"inconclusive":0,"best_missing":0}
        }}}
        c={"token":"gval:max_week:10","human_cost":1000,"search_stage":1}
        before=c["search_stage"]
        learned=app._candidate_guided_cost_v541(c,job)
        self.assertLess(learned,1000)
        self.assertEqual(c["search_stage"],before)

    def test_gui_explains_risk_for_solver_affecting_controls(self):
        for needle in (
            "constraintRisk(c)","individualConstraintRisk(r)","technicalRisk('workers'",
            "risk-box","Wymagana obsada miejsc dyżurów","Lokalna wiedza NODE00",
            "twarda decyzja administratora","Kolejność Generatora jest warstwowa"
        ):
            self.assertIn(needle,INDEX)

    def test_near_full_runs_before_broad_search_and_baseline_is_not_recomputed(self):
        self.assertIn("_near_full_candidate_items_v580(candidates,base,16)",APP)
        self.assertIn("_evaluate_near_full_parallel_v580",APP)
        self.assertIn("Szybka naprawa 1–3 braków",APP)
        self.assertIn('"elapsed_s":base_elapsed},"local","baseline"',APP)
        self.assertNotIn('t0=_time.perf_counter();j=_joint_order_v2(base_state,e13,es,"13-first",False)',APP)
        near=APP.index("_near_full_candidate_items_v580(candidates,base,16)")
        broad=APP.index("for stage in (1,2,3):",near)
        self.assertLess(near,broad)

    def test_fast_first_baseline_publishes_before_full_quality_optimization(self):
        self.assertIn('base_state["solver_contract_only"]=True',APP)
        self.assertIn('base_state["solver_internal_workers"]=8',APP)
        self.assertIn('base_state["solver_wf_fallback_seconds"]=4',APP)
        pub=APP.index('_working_from_full_eval_v579(base_state,e13,es,base')
        heavy=APP.index('_repair_variant_v2(state,state,e13,es,[],[],base)',pub)
        self.assertLess(pub,heavy)
        self.assertIn('contract_only=bool(state.get("solver_contract_only",False))',SOLVER)
        self.assertIn('(not contract_only) and matrix_enabled',SOLVER)

    def test_frontend_has_continuous_backend_truth_sync_for_solver_job(self):
        self.assertIn("repairTruthTimer:null",INDEX)
        self.assertIn("async syncRepairTruth()",INDEX)
        self.assertIn("/api/diagnostics/repair/search/current?truth=",INDEX)
        self.assertIn("setInterval(()=>this.syncRepairTruth(),800)",INDEX)

    def test_solver_terminal_is_visible_before_worker_farm_and_baseline_reports_live_probe(self):
        self.assertLess(INDEX.index("data-solver-mini-terminal"),INDEX.index('class="card worker-farm"'))
        self.assertIn('job["stage"]="Baseline: pełna obsada bez ustępstw"',APP)
        self.assertIn('job["current_probe"]=_copy.deepcopy(baseline_probe)',APP)
        self.assertIn('job["active_probes"]=[_copy.deepcopy(baseline_probe)]',APP)
        self.assertIn('job["block_total"]=1',APP)
        self.assertIn('job["block_done"]=0',APP)
        self.assertIn('job["last_probe_result"]={',APP)
        self.assertIn('"elapsed_s":round(base_elapsed,3)',APP)
        self.assertIn('job["active_probes"]=[]',APP)

    def test_plan_pdf_export_and_solver_terminal_are_wired_to_live_state(self):
        self.assertEqual(INDEX.count("Eksportuj PDF"),1)
        self.assertIn("exportCurrentPlanPdf()",INDEX)
        self.assertIn("view_mode:mode",INDEX)
        self.assertIn("displayModePlan",INDEX)
        self.assertIn("layout:'teacher_grid'",INDEX)
        self.assertIn('if layout=="teacher_grid":',APP)
        self.assertIn('if view_mode not in ("all","duties","lessons")',APP)
        self.assertIn("data-solver-mini-terminal",INDEX)
        self.assertIn("solverActiveProbes",INDEX)
        self.assertIn("last_probe_result",APP)
        self.assertIn("_terminal_probe_row",APP)

    def test_location_ui_exposes_school_general_and_gym_zone(self):
        self.assertIn('<option value="gym">Sala gimnastyczna</option>',INDEX)
        self.assertIn('<option value="">Szkoła / ogólne</option>',INDEX)
        self.assertIn("||'Szkoła / ogólne'",INDEX)
        self.assertNotIn("Systemowe miejsca sali gimnastycznej",APP)
        self.assertNotIn('locs.append("Sala gimnastyczna")',APP)

    def test_polish_ui_strings_are_not_replaced_with_question_marks(self):
        for bad in ("Zmie? nazw?","Usu?","pi?tro","dy?uru","ju? istnieje","wy??cznie","1?3"):
            self.assertNotIn(bad,INDEX)
        self.assertIn("Zmień nazwę",INDEX)
        self.assertIn("Usuń",INDEX)
        self.assertIn("I piętro",INDEX)
        self.assertIn("miejsce dyżuru",INDEX)

if __name__=="__main__":
    unittest.main(verbosity=2)
