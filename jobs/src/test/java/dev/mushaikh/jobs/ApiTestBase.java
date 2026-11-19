package dev.mushaikh.jobs;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.util.UUID;
import java.util.concurrent.atomic.AtomicInteger;

import jakarta.servlet.http.Cookie;

import org.junit.jupiter.api.BeforeEach;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;
import org.springframework.test.web.servlet.request.RequestPostProcessor;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@Import(TestDb.class)
public abstract class ApiTestBase {

	protected static final String SESSION_COOKIE = "__Host-SESSION";
	protected static final String PASSWORD = "correct horse battery";

	private static final AtomicInteger IP = new AtomicInteger(1);

	@Autowired
	protected MockMvc mvc;

	@Autowired
	protected JdbcTemplate jdbc;

	@Autowired
	protected dev.mushaikh.jobs.security.LoginAttemptService loginAttempts;

	@Autowired
	protected dev.mushaikh.jobs.job.JobQueryService jobQueries;

	@Autowired
	protected dev.mushaikh.jobs.job.TaggingStatsService taggingStats;

	@BeforeEach
	void cleanDatabase() {
		loginAttempts.clearAll();
		jobQueries.clearMetaCache();
		taggingStats.clearCache();
		jdbc.execute("truncate job_tags, apply_clicks, saved_jobs, jobs, sources, ingest_runs, users,"
				+ " spring_session_attributes, spring_session restart identity cascade");
	}

	/** A new client IP, so the per-IP rate limiter never interferes with unrelated tests. */
	protected static RequestPostProcessor freshIp() {
		int n = IP.incrementAndGet();
		return ip("10.%d.%d.%d".formatted((n >> 16) & 255, (n >> 8) & 255, n & 255));
	}

	protected static RequestPostProcessor ip(String address) {
		return request -> {
			request.setRemoteAddr(address);
			return request;
		};
	}

	protected record Csrf(Cookie cookie, String token) {
	}

	/** The real browser flow: GET /api/csrf sets XSRF-TOKEN; its value goes in X-XSRF-TOKEN. */
	protected Csrf csrf() throws Exception {
		MvcResult result = mvc.perform(get("/api/csrf").with(freshIp())).andExpect(status().isOk()).andReturn();
		Cookie cookie = result.getResponse().getCookie("XSRF-TOKEN");
		return new Csrf(cookie, cookie.getValue());
	}

	/** Adds a valid CSRF cookie + header and a fresh IP to a state-changing request. */
	protected MockHttpServletRequestBuilder mutating(MockHttpServletRequestBuilder builder, Cookie... session)
			throws Exception {
		Csrf csrf = csrf();
		builder.cookie(csrf.cookie()).header("X-XSRF-TOKEN", csrf.token()).with(freshIp());
		if (session.length > 0) {
			builder.cookie(session);
		}
		return builder;
	}

	protected static String json(String email, String password, String name) {
		String body = "{\"email\":\"%s\",\"password\":\"%s\"".formatted(email, password);
		return name == null ? body + "}" : body + ",\"name\":\"%s\"}".formatted(name);
	}

	protected MvcResult register(String email, String password) throws Exception {
		return mvc
			.perform(mutating(post("/api/auth/register")).contentType(MediaType.APPLICATION_JSON)
				.content(json(email, password, "Test User")))
			.andReturn();
	}

	protected MvcResult login(String email, String password, Cookie... existing) throws Exception {
		return mvc
			.perform(mutating(post("/api/auth/login"), existing).contentType(MediaType.APPLICATION_JSON)
				.content(json(email, password, null)))
			.andReturn();
	}

	/** Value of the session cookie set by a response, or null. */
	protected static Cookie sessionCookie(MvcResult result) {
		for (String header : result.getResponse().getHeaders("Set-Cookie")) {
			if (header.startsWith(SESSION_COOKIE + "=")) {
				String value = header.substring(SESSION_COOKIE.length() + 1).split(";", 2)[0];
				return value.isEmpty() ? null : new Cookie(SESSION_COOKIE, value);
			}
		}
		return null;
	}

	protected static String setCookieHeader(MvcResult result, String name) {
		return result.getResponse()
			.getHeaders("Set-Cookie")
			.stream()
			.filter(h -> h.startsWith(name + "="))
			.findFirst()
			.orElse(null);
	}

	protected Cookie registerAndLogin(String email) throws Exception {
		register(email, PASSWORD);
		return sessionCookie(login(email, PASSWORD));
	}

	protected long sourceId(String key, String type) {
		jdbc.update("insert into sources (key, type) values (?, ?) on conflict (key) do nothing", key, type);
		return jdbc.queryForObject("select id from sources where key = ?", Long.class, key);
	}

	protected UUID insertJob(String title, String company, String description, String applyUrl) {
		UUID id = UUID.randomUUID();
		jdbc.update("""
				insert into jobs (id, source_id, external_id, title, company, location_raw, description_text,
				                  apply_url, content_hash, dedupe_key)
				values (?, ?, ?, ?, ?, 'Bengaluru, India', ?, ?, 'hash', ?)
				""", id, sourceId("greenhouse:test", "greenhouse"), id.toString(), title, company, description,
				applyUrl, id.toString());
		return id;
	}

	protected void tag(UUID jobId, String role, String city, String mode, String type, Integer expMin,
			boolean fresher) {
		jdbc.update("""
				insert into job_tags (job_id, role_category, role_title_clean, city, state, work_mode, job_type,
				                      experience_min, experience_max, is_fresher, model, prompt_version)
				values (?, ?, 'Clean Title', ?, null, ?, ?, ?, null, ?, 'test', 'v1')
				""", jobId, role, city, mode, type, expMin, fresher);
	}
}
