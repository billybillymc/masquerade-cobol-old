"""Tests for jcl_parser.py — JCL job/step/DD parsing."""
import sys
from pathlib import Path
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jcl_parser import parse_jcl_file, JclIndex


def _write_jcl(tmp_dir, name, content):
    p = Path(tmp_dir) / f"{name}.jcl"
    p.write_text(content, encoding="utf-8")
    return p


class TestJclParsing:
    def test_single_step_job(self, tmp_path):
        _write_jcl(tmp_path, "MYJOB", """//MYJOB    JOB 'TEST',CLASS=A,MSGCLASS=0
//* Run the batch processor
//STEP01  EXEC PGM=BATCHPGM
//INFILE  DD DISP=SHR,DSN=MY.INPUT.FILE
//OUTFILE DD DISP=(NEW,CATLG),DSN=MY.OUTPUT.FILE
""")
        job = parse_jcl_file(tmp_path / "MYJOB.jcl")
        assert job is not None
        assert job.name == "MYJOB"
        assert len(job.steps) == 1
        assert job.steps[0].program == "BATCHPGM"
        assert len(job.steps[0].dd_statements) == 2

    def test_multi_step_job(self, tmp_path):
        _write_jcl(tmp_path, "MULTI", """//MULTI   JOB 'MULTI-STEP',CLASS=A
//STEP01  EXEC PGM=SORT
//SORTIN  DD DISP=SHR,DSN=RAW.DATA
//SORTOUT DD DISP=(NEW,CATLG),DSN=SORTED.DATA
//STEP02  EXEC PGM=PROCESS,COND=(0,NE)
//INPUT   DD DISP=SHR,DSN=SORTED.DATA
//OUTPUT  DD DISP=(NEW,CATLG),DSN=RESULT.DATA
""")
        job = parse_jcl_file(tmp_path / "MULTI.jcl")
        assert len(job.steps) == 2
        assert job.steps[0].program == "SORT"
        assert job.steps[1].program == "PROCESS"
        assert job.steps[1].condition == "0,NE"

    def test_input_output_classification(self, tmp_path):
        _write_jcl(tmp_path, "IO", """//IO      JOB 'IO',CLASS=A
//STEP01  EXEC PGM=MYPGM
//INP1    DD DISP=SHR,DSN=READ.THIS
//INP2    DD DISP=(OLD),DSN=UPDATE.THIS
//OUT1    DD DISP=(NEW,CATLG),DSN=WRITE.THIS
//OUT2    DD DISP=(MOD,CATLG),DSN=APPEND.THIS
""")
        job = parse_jcl_file(tmp_path / "IO.jcl")
        step = job.steps[0]
        assert "READ.THIS" in step.input_datasets
        assert "UPDATE.THIS" in step.input_datasets
        assert "WRITE.THIS" in step.output_datasets
        assert "APPEND.THIS" in step.output_datasets

    def test_programs_excludes_utilities(self, tmp_path):
        _write_jcl(tmp_path, "UTILS", """//UTILS   JOB 'UTILS',CLASS=A
//STEP01  EXEC PGM=IDCAMS
//STEP02  EXEC PGM=MYBATCH
""")
        job = parse_jcl_file(tmp_path / "UTILS.jcl")
        assert job.programs == ["MYBATCH"]
        assert job.all_programs == ["IDCAMS", "MYBATCH"]


class TestJclIndex:
    def test_index_and_flows(self, tmp_path):
        _write_jcl(tmp_path, "PRODUCER", """//PRODUCER JOB 'P',CLASS=A
//STEP01  EXEC PGM=EXTRACT
//OUTPUT  DD DISP=(NEW,CATLG),DSN=SHARED.DATA.SET
""")
        _write_jcl(tmp_path, "CONSUMER", """//CONSUMER JOB 'C',CLASS=A
//STEP01  EXEC PGM=LOAD
//INPUT   DD DISP=SHR,DSN=SHARED.DATA.SET
""")
        idx = JclIndex(str(tmp_path))
        assert idx.summary()["total_jobs"] == 2

        flows = idx.dataset_flow()
        assert len(flows) == 1
        assert flows[0]["producer"] == "PRODUCER"
        assert flows[0]["consumer"] == "CONSUMER"

    def test_execution_order(self, tmp_path):
        _write_jcl(tmp_path, "FIRST", """//FIRST   JOB 'F',CLASS=A
//STEP01  EXEC PGM=GEN
//OUT     DD DISP=(NEW,CATLG),DSN=STAGE.FILE
""")
        _write_jcl(tmp_path, "SECOND", """//SECOND  JOB 'S',CLASS=A
//STEP01  EXEC PGM=USE
//IN      DD DISP=SHR,DSN=STAGE.FILE
""")
        _write_jcl(tmp_path, "INDEP", """//INDEP   JOB 'I',CLASS=A
//STEP01  EXEC PGM=SOLO
//DATA    DD DISP=SHR,DSN=OTHER.FILE
""")
        idx = JclIndex(str(tmp_path))
        layers = idx.execution_order()
        assert len(layers) == 2
        assert "FIRST" in layers[0]
        assert "INDEP" in layers[0]
        assert "SECOND" in layers[1]

    def test_jobs_for_program(self, tmp_path):
        _write_jcl(tmp_path, "JOB1", """//JOB1    JOB 'J',CLASS=A
//STEP01  EXEC PGM=SHARED
""")
        _write_jcl(tmp_path, "JOB2", """//JOB2    JOB 'J',CLASS=A
//STEP01  EXEC PGM=SHARED
""")
        idx = JclIndex(str(tmp_path))
        jobs = idx.jobs_for_program("SHARED")
        assert "JOB1" in jobs
        assert "JOB2" in jobs
