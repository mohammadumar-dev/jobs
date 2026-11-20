package dev.mushaikh.jobs;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.hasSize;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.util.UUID;

import jakarta.servlet.http.Cookie;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class JobApiTests extends ApiTestBase {

	UUID backendIntern;
	UUID dataAnalyst;
	UUID designer;

	@BeforeEach
	void seed() {
		backendIntern = insertJob("Backend Engineer Intern", "Acme", "Build Java services with Spring.",
				"https://boards.example.com/acme/1");
		tag(backendIntern, "software", "Bengaluru", "hybrid", "internship", 0, true);
		dataAnalyst = insertJob("Graduate Data Analyst", "Globex", "SQL dashboards and reporting.",
				"https://boards.example.com/globex/2");
		tag(dataAnalyst, "data", "Pune", "onsite", "full_time", 1, true);
		designer = insertJob("Junior Product Designer", "Initech", "Figma and user research.",
				"https://boards.example.com/initech/3");
		tag(designer, "design", "Remote", "remote", "full_time", 2, true);
	}

	// --- listing ----------------------------------------------------------------

	@Test
	void listsActiveFresherJobsPubliclyWithTags() throws Exception {
		mvc.perform(get("/api/jobs").with(freshIp()))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.total").value(3))
			.andExpect(jsonPath("$.items", hasSize(3)))
			.andExpect(jsonPath("$.items[0].tags.roleCategory").exists())
			.andExpect(jsonPath("$.items[0].sourceType").value("greenhouse"))
			.andExpect(jsonPath("$.items[0].description").doesNotExist());
	}

	@Test
	void hidesInactiveDuplicateAndNonFresherJobsButShowsUntagged() throws Exception {
		UUID inactive = insertJob("Old Intern", "Acme", "x", "https://boards.example.com/4");
		jdbc.update("update jobs set is_active = false where id = ?", inactive);
		UUID duplicate = insertJob("Backend Engineer Intern", "Acme", "x", "https://other.example.com/5");
		jdbc.update("update jobs set canonical_job_id = ? where id = ?", backendIntern, duplicate);
		UUID senior = insertJob("Associate Architect", "Acme", "x", "https://boards.example.com/6");
		tag(senior, "software", "Pune", "onsite", "full_time", 6, false);
		UUID untagged = insertJob("Support Trainee", "Acme", "x", "https://boards.example.com/7");

		mvc.perform(get("/api/jobs").with(freshIp()))
			.andExpect(jsonPath("$.total").value(4))
			.andExpect(jsonPath("$.items[?(@.id=='%s')]".formatted(untagged)).exists())
			.andExpect(jsonPath("$.items[?(@.id=='%s')].tags".formatted(untagged)).value(new java.util.ArrayList<>(
					java.util.Collections.singletonList(null))))
			.andExpect(jsonPath("$.items[?(@.id=='%s')]".formatted(inactive)).doesNotExist())
			.andExpect(jsonPath("$.items[?(@.id=='%s')]".formatted(duplicate)).doesNotExist())
			.andExpect(jsonPath("$.items[?(@.id=='%s')]".formatted(senior)).doesNotExist());
	}

	@Test
	void filtersByRoleCityModeTypeAndExperience() throws Exception {
		mvc.perform(get("/api/jobs?role=data").with(freshIp()))
			.andExpect(jsonPath("$.total").value(1))
			.andExpect(jsonPath("$.items[0].id").value(dataAnalyst.toString()));
		mvc.perform(get("/api/jobs?city=Bengaluru").with(freshIp()))
			.andExpect(jsonPath("$.items[0].id").value(backendIntern.toString()));
		mvc.perform(get("/api/jobs?mode=remote").with(freshIp()))
			.andExpect(jsonPath("$.items[0].id").value(designer.toString()));
		mvc.perform(get("/api/jobs?type=internship").with(freshIp())).andExpect(jsonPath("$.total").value(1));
		mvc.perform(get("/api/jobs?exp=0").with(freshIp())).andExpect(jsonPath("$.total").value(1));
		mvc.perform(get("/api/jobs?exp=1").with(freshIp())).andExpect(jsonPath("$.total").value(2));
		mvc.perform(get("/api/jobs?role=data&city=Bengaluru").with(freshIp())).andExpect(jsonPath("$.total").value(0));
	}

	@Test
	void fullTextSearchCoversTitleCompanyAndDescription() throws Exception {
		mvc.perform(get("/api/jobs?q=spring").with(freshIp()))
			.andExpect(jsonPath("$.total").value(1))
			.andExpect(jsonPath("$.items[0].id").value(backendIntern.toString()));
		mvc.perform(get("/api/jobs?q=globex").with(freshIp())).andExpect(jsonPath("$.total").value(1));
		mvc.perform(get("/api/jobs?q=designers").with(freshIp())).andExpect(jsonPath("$.total").value(1)); // stemming
		mvc.perform(get("/api/jobs?q=kubernetes").with(freshIp())).andExpect(jsonPath("$.total").value(0));
	}

	@Test
	void paginates() throws Exception {
		for (int i = 0; i < 22; i++) {
			insertJob("Trainee " + i, "Acme", "x", "https://boards.example.com/t" + i);
		}
		mvc.perform(get("/api/jobs").with(freshIp()))
			.andExpect(jsonPath("$.total").value(25))
			.andExpect(jsonPath("$.totalPages").value(2))
			.andExpect(jsonPath("$.items", hasSize(20)));
		mvc.perform(get("/api/jobs?page=2").with(freshIp())).andExpect(jsonPath("$.items", hasSize(5)));
		mvc.perform(get("/api/jobs?page=9").with(freshIp())).andExpect(jsonPath("$.items", hasSize(0)));
	}

	@Test
	void rejectsInvalidParametersAndTreatsSqlAsPlainText() throws Exception {
		mvc.perform(get("/api/jobs?page=0").with(freshIp())).andExpect(status().isBadRequest());
		mvc.perform(get("/api/jobs?exp=-1").with(freshIp())).andExpect(status().isBadRequest());
		mvc.perform(get("/api/jobs?exp=abc").with(freshIp())).andExpect(status().isBadRequest());
		mvc.perform(get("/api/jobs").param("role", "data' or '1'='1").with(freshIp()))
			.andExpect(status().isBadRequest());
		mvc.perform(get("/api/jobs").param("q", "x".repeat(101)).with(freshIp())).andExpect(status().isBadRequest());
		mvc.perform(get("/api/jobs/not-a-uuid").with(freshIp())).andExpect(status().isBadRequest());
		// free-text search is a bound parameter: injection attempts just match nothing
		mvc.perform(get("/api/jobs").param("q", "'; drop table jobs; --").with(freshIp()))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.total").value(0));
		assertThat(jdbc.queryForObject("select count(*) from jobs", Integer.class)).isEqualTo(3);
	}

	// --- detail -----------------------------------------------------------------

	@Test
	void detailStripsAllMarkupFromDescription() throws Exception {
		UUID dirty = insertJob("Intern", "Acme",
				"Line one\n<script>alert('xss')</script><img src=x onerror=alert(1)><b>Bold</b> & plain",
				"https://boards.example.com/8");
		String body = mvc.perform(get("/api/jobs/" + dirty).with(freshIp()))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.applyUrl").value("https://boards.example.com/8"))
			.andReturn()
			.getResponse()
			.getContentAsString();
		assertThat(body).doesNotContain("<script").doesNotContain("onerror").doesNotContain("<b>").doesNotContain("<img");
		assertThat(body).contains("Line one\\n").contains("Bold & plain");
	}

	@Test
	void detailOfUnknownJobIs404() throws Exception {
		mvc.perform(get("/api/jobs/" + UUID.randomUUID()).with(freshIp())).andExpect(status().isNotFound());
	}

	// --- apply (no open redirect) -------------------------------------------------

	@Test
	void applyRecordsTheClickAndReturnsTheSourceUrl() throws Exception {
		mvc.perform(mutating(post("/api/jobs/" + backendIntern + "/apply")))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.applyUrl").value("https://boards.example.com/acme/1"));
		assertThat(jdbc.queryForObject("select count(*) from apply_clicks where user_id is null", Integer.class))
			.isEqualTo(1);

		Cookie session = registerAndLogin("a@example.com");
		mvc.perform(mutating(post("/api/jobs/" + backendIntern + "/apply"), session)).andExpect(status().isOk());
		assertThat(jdbc.queryForObject("select count(*) from apply_clicks where user_id is not null", Integer.class))
			.isEqualTo(1);
	}

	@Test
	void applyNeverReturnsANonHttpUrl() throws Exception {
		for (String bad : new String[] { "javascript:alert(1)", "data:text/html,<script>1</script>",
				"//evil.example/path", "ftp://files.example.com/x", "/relative/path" }) {
			UUID job = insertJob("Intern", "Acme", "x", bad);
			mvc.perform(mutating(post("/api/jobs/" + job + "/apply"))).andExpect(status().isUnprocessableEntity());
			mvc.perform(get("/api/jobs/" + job).with(freshIp())).andExpect(jsonPath("$.applyUrl").doesNotExist());
		}
		assertThat(jdbc.queryForObject("select count(*) from apply_clicks", Integer.class)).isZero();
		// the URL cannot be supplied by the caller: extra parameters are ignored
		mvc.perform(mutating(post("/api/jobs/" + backendIntern + "/apply")).param("url", "https://evil.example"))
			.andExpect(jsonPath("$.applyUrl").value("https://boards.example.com/acme/1"));
	}

	@Test
	void applyNeedsCsrfAndAKnownJob() throws Exception {
		mvc.perform(post("/api/jobs/" + backendIntern + "/apply").with(freshIp())).andExpect(status().isForbidden());
		mvc.perform(mutating(post("/api/jobs/" + UUID.randomUUID() + "/apply"))).andExpect(status().isNotFound());
	}

	// --- saved / applied dashboard --------------------------------------------------

	@Test
	void savingRequiresLogin() throws Exception {
		mvc.perform(mutating(post("/api/jobs/" + backendIntern + "/save"))).andExpect(status().isUnauthorized());
		assertThat(jdbc.queryForObject("select count(*) from saved_jobs", Integer.class)).isZero();
	}

	@Test
	void saveListUnsaveAndAppliedAreScopedToTheUser() throws Exception {
		Cookie alice = registerAndLogin("alice@example.com");
		Cookie bob = registerAndLogin("bob@example.com");

		mvc.perform(mutating(post("/api/jobs/" + backendIntern + "/save"), alice)).andExpect(status().isNoContent());
		mvc.perform(mutating(post("/api/jobs/" + backendIntern + "/save"), alice)).andExpect(status().isNoContent()); // idempotent
		mvc.perform(mutating(post("/api/jobs/" + designer + "/apply"), alice)).andExpect(status().isOk());
		mvc.perform(mutating(post("/api/jobs/" + designer + "/apply"), alice)).andExpect(status().isOk());
		mvc.perform(mutating(post("/api/jobs/" + UUID.randomUUID() + "/save"), alice)).andExpect(status().isNotFound());

		mvc.perform(get("/api/me/saved").cookie(alice))
			.andExpect(jsonPath("$", hasSize(1)))
			.andExpect(jsonPath("$[0].job.id").value(backendIntern.toString()))
			.andExpect(jsonPath("$[0].at").exists());
		mvc.perform(get("/api/me/applied").cookie(alice))
			.andExpect(jsonPath("$", hasSize(1))) // two clicks, one job
			.andExpect(jsonPath("$[0].job.id").value(designer.toString()));
		mvc.perform(get("/api/me/saved").cookie(bob)).andExpect(jsonPath("$", hasSize(0)));
		mvc.perform(get("/api/me/applied").cookie(bob)).andExpect(jsonPath("$", hasSize(0)));

		mvc.perform(mutating(delete("/api/jobs/" + backendIntern + "/save"), alice)).andExpect(status().isNoContent());
		mvc.perform(get("/api/me/saved").cookie(alice)).andExpect(jsonPath("$", hasSize(0)));
	}

	// --- meta -------------------------------------------------------------------

	@Test
	void metaReportsCountsFacetsAndLastRefresh() throws Exception {
		jdbc.update("insert into ingest_runs (finished_at) values (now())");
		mvc.perform(get("/api/meta"))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.lastRefresh").exists())
			.andExpect(jsonPath("$.roles").isArray())
			.andExpect(jsonPath("$.cities").isArray())
			.andExpect(jsonPath("$.workModes").isArray())
			.andExpect(jsonPath("$.jobTypes").isArray());
	}

	@Test
	void taggingStatsPriceFreeTokensAtTheReferenceModel() throws Exception {
		// seeded rows: model 'test', no tokens (counts as non-LLM). Add two free-tier LLM rows.
		UUID a = insertJob("Intern A", "Acme", "x", "https://boards.example.com/a");
		tag(a, "software", "Pune", "onsite", "internship", 0, true);
		UUID b = insertJob("Intern B", "Acme", "x", "https://boards.example.com/b");
		tag(b, "software", "Pune", "onsite", "internship", 0, true);
		jdbc.update("update job_tags set model = 'gemini/gemini-3.5-flash-lite', input_tokens = 1000,"
				+ " output_tokens = 100 where job_id in (?, ?)", a, b);
		jdbc.update("insert into ingest_runs (finished_at, tagged, llm_cost_usd) values (now(), 2, 0)");

		// 1000 in @ $0.10/M + 100 out @ $0.50/M = $0.00015 per job = $0.15 per 1,000
		mvc.perform(get("/api/meta/tagging").with(freshIp()))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.jobsTagged").value(5))
			.andExpect(jsonPath("$.llmTaggedJobs").value(2))
			.andExpect(jsonPath("$.models[0].model").value("test"))
			.andExpect(jsonPath("$.models[1].model").value("gemini/gemini-3.5-flash-lite"))
			.andExpect(jsonPath("$.models[1].percent").value(40.0))
			.andExpect(jsonPath("$.avgInputTokens").value(1000.0))
			.andExpect(jsonPath("$.actualCostUsd").value(0.0))
			.andExpect(jsonPath("$.actualPer1000Usd").value(0.0))
			.andExpect(jsonPath("$.referenceModel").value("claude-haiku-5-5"))
			.andExpect(jsonPath("$.paidPer1000Usd").value(0.15))
			.andExpect(jsonPath("$.paidPer1000Inr").value(13.2))
			.andExpect(jsonPath("$.lastRun").exists());
	}

	@Test
	void taggingStatsAreEmptyBeforeAnyLlmRun() throws Exception {
		jdbc.update("truncate job_tags");
		mvc.perform(get("/api/meta/tagging").with(freshIp()))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.jobsTagged").value(0))
			.andExpect(jsonPath("$.paidPer1000Usd").doesNotExist())
			.andExpect(jsonPath("$.actualPer1000Usd").doesNotExist());
	}

	@Test
	void runHistoryShowsRecentRunsNewestFirstWithErrorCountsOnly() throws Exception {
		insertJob("Intern A", "Acme", "x", "https://boards.example.com/a");
		jdbc.update("""
				insert into ingest_runs (started_at, finished_at, fetched, new, tagged, errors_json)
				values (now() - interval '2 days', now() - interval '2 days' + interval '90 seconds', 100, 10, 8,
				        '[{"source": "lever:x", "error": "secret detail"}]'::jsonb)
				""");
		jdbc.update("insert into ingest_runs (started_at, fetched) values (now(), 50)"); // still running

		mvc.perform(get("/api/meta/runs").with(freshIp()))
			.andExpect(status().isOk())
			.andExpect(jsonPath("$.runs.length()").value(2))
			.andExpect(jsonPath("$.runs[0].fetched").value(50))
			.andExpect(jsonPath("$.runs[0].finishedAt").doesNotExist())
			.andExpect(jsonPath("$.runs[1].durationSeconds").value(90))
			.andExpect(jsonPath("$.runs[1].newJobs").value(10))
			.andExpect(jsonPath("$.runs[1].tagged").value(8))
			.andExpect(jsonPath("$.runs[1].errors").value(1))
			.andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("secret detail"))))
			.andExpect(jsonPath("$.sources[0].type").value("greenhouse"))
			.andExpect(jsonPath("$.sources[0].percent").value(100.0));
	}
}
