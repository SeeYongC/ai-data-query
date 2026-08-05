"""LLM-powered SQL agent - complete rewrite with all features."""
import json, re
from openai import AsyncOpenAI
from .database import Database

TEMPLATE = """You are an expert SQL analyst. Use ONLY the tables and columns listed below.

## DATABASES AND TABLES (ONLY SOURCE OF TRUTH)

{ALL_SCHEMAS}

## RULES

1. ONLY use table/column names from above. If not listed, it does NOT exist.
2. For percentages multiply by 100.0 after division. Use ROUND(val,2) for money.
3. Limit to 50 rows max unless asked for more.
{EXTRA}

## OUTPUT

Return ONLY: {{"sql":"...","explanation":"..."}}"""


class Agent:
    def __init__(self, db: Database, api_key: str, model="gpt-4o", base_url=None):
        self.db = db
        self.all_dbs = {}
        kw = {"api_key": api_key}
        if base_url: kw["base_url"] = base_url
        self.client = AsyncOpenAI(**kw)
        self.model = model
        self.governance = None

    def set_governance(self, g): self.governance = g
    def set_all_databases(self, dbs): self.all_dbs = dbs

    def _get_db(self, name=None):
        if name and name in self.all_dbs: return self.all_dbs[name]
        if self.all_dbs: return list(self.all_dbs.values())[0]
        return self.db

    READ_WRITE_KW = ("insert", "update", "delete", "drop", "alter", "create",
                     "replace", "truncate", "merge", "grant", "revoke", "into")

    @staticmethod
    def _strip_literals(s: str) -> str:
        """Remove string literals and comments so write-keyword scanning ignores them."""
        return re.sub(r"'[^']*'|\"[^\"]*\"|--[^\n]*|/\*.*?\*/", "", s, flags=re.DOTALL)

    def _is_read_only(self, sql: str) -> bool:
        """Allow only read-only statements (SELECT / WITH ... SELECT)."""
        s = sql.strip().lstrip("(").lstrip()
        if not s:
            return False
        stripped = self._strip_literals(s)
        # Reject multi-statement input (semicolons inside string literals are already removed).
        body = stripped.rstrip()
        if body.endswith(";"):
            body = body[:-1]
        if ";" in body:
            return False
        first = s.split(None, 1)[0].lower().rstrip(";")
        if first == "select":
            return not any(re.search(r"\b" + k + r"\b", stripped, re.IGNORECASE) for k in self.READ_WRITE_KW)
        if first == "with":
            # WITH x AS (...) SELECT ... is read-only; CTE write statements are not.
            return not any(re.search(r"\b" + k + r"\b", stripped[4:], re.IGNORECASE) for k in self.READ_WRITE_KW)
        return False

    def _execute_readonly(self, db, sql):
        """Execute SQL only if it is read-only (SELECT/WITH), else raise."""
        if not self._is_read_only(sql):
            raise ValueError("仅支持只读查询（SELECT / WITH ... SELECT），已拒绝写操作")
        return db.execute(sql)

    def _build_prompt(self, metric_ctx="", db_name=None):
        dbs = {db_name: self.all_dbs[db_name]} if db_name and db_name in self.all_dbs else self.all_dbs
        parts = []
        for name, db in dbs.items():
            try:
                s = db.get_schema()
                tbls = re.findall(r"CREATE TABLE (\w+)", s, re.IGNORECASE)
                parts.append("### %s\nTables: %s\n```sql\n%s\n```" % (name, ", ".join(tbls) if tbls else "unknown", s))
            except Exception as e:
                parts.append("### %s\n(Error: %s)" % (name, e))
        if not parts:
            parts.append("### default\n```sql\n%s\n```" % self.db.get_schema())
        extra = "\n\n" + metric_ctx if metric_ctx else ""
        return TEMPLATE.replace("{ALL_SCHEMAS}", "\n\n".join(parts)).replace("{EXTRA}", extra)

    @staticmethod
    def _split_refs(refs: str) -> list[str]:
        """Split comma-separated table refs, ignoring commas inside quoted identifiers."""
        parts, cur, q = [], "", None
        for ch in refs:
            if q:
                cur += ch
                if ch == q:
                    q = None
            elif ch in ('"', "'", "`"):
                q = ch
                cur += ch
            elif ch == ",":
                parts.append(cur)
                cur = ""
            else:
                cur += ch
        if cur.strip():
            parts.append(cur)
        return parts

    def _validate_sql_tables(self, sql, db):
        try:
            real = set(t.lower() for t in db.inspector.get_table_names())
            kw = {"select","from","where","and","or","not","in","join","on","as","group","by","order","limit","having",
                  "case","when","then","else","end","count","sum","avg","min","max","distinct","inner","left","right",
                  "outer","cross","union","all","null","is","like","between","exists","cast","coalesce","date","now",
                  "strftime","interval","round","asc","desc","if","nullif","datetime","extract","year","month","day",
                  "hour","substr","replace","trim","upper","lower","length","into","values","set","update","delete",
                  "insert","create","table","drop","alter","index"}
            # Match the table reference list right after FROM/JOIN, up to the next clause keyword,
            # a closing paren (subquery) or end of string. Handles "FROM t1, t2", "FROM schema.table",
            # quoted identifiers and aliases, while skipping subqueries like "FROM (SELECT ...)".
            pattern = re.compile(
                r"\b(?:FROM|JOIN)\s+(?P<refs>[^();]+?)"
                r"(?=\s+(?:WHERE|GROUP|ORDER|LIMIT|HAVING|ON|UNION|SET|VALUES|RETURNING|INNER|LEFT|RIGHT|FULL|CROSS|OUTER|FROM|JOIN)\b|\)|$)",
                re.IGNORECASE | re.DOTALL,
            )
            for m in pattern.finditer(sql):
                refs = m.group("refs")
                for part in self._split_refs(refs):
                    # Strip schema prefix and alias; keep quoted identifiers whole (may contain spaces, dots, commas).
                    name = part.strip()
                    if not name:
                        continue
                    if name[:1] in ('"', "'", "`"):
                        q = name[0]
                        tbl = name[1:name.rfind(q)] if q in name[1:] else name.strip(q)
                    else:
                        tbl = name.split(".")[-1].split()[0]
                    if tbl.lower() not in real and tbl.lower() not in kw and not tbl.isdigit():
                        return "Table '%s' does not exist. Available tables: %s" % (tbl, ", ".join(sorted(real)))
            return None
        except Exception:
            return None

    async def query(self, question, metric_selections=None, selected_database=None):
        mc = ""
        if metric_selections and self.governance:
            mc = self.governance.inject_context(metric_selections)
            for mk, did in metric_selections.items():
                try: self.governance.save_preference("default", mk, did)
                except Exception: pass

        if not metric_selections and self.governance:
            cf = self.governance.detect_metrics(question)
            if cf:
                return {"success": False, "metric_conflict": True, "conflicts": cf, "question": question, "sql": "", "explanation": ""}

        db_names = list(self.all_dbs.keys())
        if len(db_names) > 1 and not selected_database:
            mentioned = None
            for n in db_names:
                if n.lower() in question.lower(): mentioned = n; break
            if mentioned:
                selected_database = mentioned
            else:
                infos = []
                for n in db_names:
                    db = self.all_dbs[n]
                    try:
                        tbls = db.inspector.get_table_names()
                        ut = [t for t in tbls if not t.startswith("metric_") and not t.startswith("user_metric_")]
                        infos.append({"name": n, "table_count": len(ut), "tables": sorted(ut)[:5]})
                    except Exception:
                        infos.append({"name": n, "table_count": 0, "tables": []})
                return {"success": False, "database_select": True, "databases": infos, "question": question, "sql": "", "explanation": ""}

        prompt = self._build_prompt(mc, selected_database)
        raw = await self._call_llm(question, prompt)
        sql, expl = self._parse(raw)
        if sql is None:
            return {"success": False, "error": "无法提取SQL", "sql": "", "explanation": "", "raw_response": raw[:500]}

        tdb = self._get_db(selected_database)

        # Pre-exec validation
        verr = self._validate_sql_tables(sql, tdb)
        if verr:
            prompt2 = prompt + "\n\n## VALIDATION ERROR\n%s\n\nRewrite using ONLY tables from the available list. Return corrected JSON." % verr
            raw2 = await self._call_llm(question, prompt2)
            s2, e2 = self._parse(raw2)
            if s2: sql, expl = s2, e2 or expl

        try:
            cols, rows = self._execute_readonly(tdb, sql)
            return {"success": True, "sql": sql, "explanation": expl, "columns": cols, "rows": rows, "row_count": len(rows), "retried": False}
        except Exception as e:
            tbl_list = "unknown"
            try: tbl_list = ", ".join(sorted(tdb.inspector.get_table_names()))
            except: pass
            db_lbl = selected_database or (db_names[0] if db_names else "current")
            prompt3 = prompt + "\n\n## FAILED\nSQL: %s\nError: %s\nDB '%s' tables: %s\n\nUse ONLY tables/columns from above. Return corrected JSON." % (sql, str(e), db_lbl, tbl_list)
            raw3 = await self._call_llm(question, prompt3)
            s3, e3 = self._parse(raw3)
            if s3 is None: s3, e3 = sql, expl
            try:
                cols, rows = self._execute_readonly(tdb, s3)
                return {"success": True, "sql": s3, "explanation": e3 or expl, "columns": cols, "rows": rows, "row_count": len(rows), "retried": True, "first_error": str(e)}
            except Exception as e2:
                return {"success": False, "sql": s3, "explanation": e3 or expl, "error": str(e2), "first_error": str(e)}

    async def _call_llm(self, q, prompt):
        r = await self.client.chat.completions.create(model=self.model, messages=[
            {"role": "system", "content": prompt}, {"role": "user", "content": "Q: " + q + "\nA:"}
        ], temperature=0.1, max_tokens=1000)
        return r.choices[0].message.content or ""

    def _parse(self, text):
        if not text: return None, ""
        text = text.strip()
        try:
            d = json.loads(text); return d.get("sql", ""), d.get("explanation", "")
        except: pass
        m = re.search(r"```(?:json)?\s*\n?(\{.*?\})\n?\s*```", text, re.DOTALL)
        if m:
            try:
                d = json.loads(m.group(1)); return d.get("sql", ""), d.get("explanation", "")
            except: pass
        for m in re.finditer(r'\{[^{}]*?"sql"\s*:\s*".*?"\s*[,}][^{}]*?"explanation"\s*:\s*".*?"\s*[,}][^{}]*?\}', text, re.DOTALL):
            try:
                d = json.loads(m.group(0))
                if "sql" in d: return d.get("sql", ""), d.get("explanation", "")
            except: continue
        sm = re.search(r'"sql"\s*:\s*"(.*?)(?<!\\)"(?=\s*(?:[,}]|"|$))', text, re.DOTALL)
        if sm:
            em = re.search(r'"explanation"\s*:\s*"(.*?)(?<!\\)"', text, re.DOTALL)
            sql = sm.group(1)
            try: sql = json.loads('"' + sql + '"')
            except Exception: pass
            expl = em.group(1) if em else ""
            try: expl = json.loads('"' + expl + '"')
            except Exception: pass
            return sql, expl
        return None, text[:300]
