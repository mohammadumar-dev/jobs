package dev.mushaikh.jobs;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.options;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import jakarta.servlet.http.Cookie;

import org.junit.jupiter.api.Test;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MvcResult;

import dev.mushaikh.jobs.user.User;
import dev.mushaikh.jobs.user.UserRepository;
import dev.mushaikh.jobs.user.UserService;

/** One test per rule in PLAN.md section 5.3. */
class AuthSecurityTests extends ApiTestBase {

	@Autowired
	UserService userService;

	@Autowired
	UserRepository userRepository;

	// --- sessions ---------------------------------------------------------------

	@Test
	void loginSetsHardenedServerSideSessionCookie() throws Exception {
		register("a@example.com", PASSWORD);
		MvcResult result = login("a@example.com", PASSWORD);

		assertThat(result.getResponse().getStatus()).isEqualTo(200);
		String cookie = setCookieHeader(result, SESSION_COOKIE);
		assertThat(cookie).startsWith("__Host-SESSION=")
			.contains("HttpOnly")
			.contains("Secure")
			.contains("SameSite=Lax")
			.contains("Path=/")
			.contains("Max-Age=604800") // 7 days
			.doesNotContain("Domain=");
		// the session lives in Postgres, not in a token
		assertThat(jdbc.queryForObject("select count(*) from spring_session", Integer.class)).isEqualTo(1);
		assertThat(jdbc.queryForObject("select max_inactive_interval from spring_session", Integer.class))
			.isEqualTo(604800); // 7-day idle timeout
		assertThat(result.getResponse().getContentAsString()).doesNotContain("token").doesNotContain("password");
	}

	@Test
	void sessionCookieAuthenticatesAndLogoutEndsIt() throws Exception {
		Cookie session = registerAndLogin("a@example.com");

		mvc.perform(get("/api/me").cookie(session))
			.andExpect(jsonPath("$.authenticated").value(true))
			.andExpect(jsonPath("$.email").value("a@example.com"));

		mvc.perform(mutating(post("/api/auth/logout"), session)).andExpect(status().isNoContent());

		mvc.perform(get("/api/me").cookie(session)).andExpect(jsonPath("$.authenticated").value(false));
		assertThat(jdbc.queryForObject("select count(*) from spring_session", Integer.class)).isZero();
	}

	@Test
	void sessionIdIsRotatedOnLogin() throws Exception {
		register("a@example.com", PASSWORD);
		// an attacker-planted id is never adopted
		MvcResult planted = login("a@example.com", PASSWORD, new Cookie(SESSION_COOKIE, "YXR0YWNrZXI="));
		assertThat(sessionCookie(planted).getValue()).isNotEqualTo("YXR0YWNrZXI=");

		// logging in again over a live session issues a new id and kills the old one
		Cookie first = sessionCookie(planted);
		Cookie second = sessionCookie(login("a@example.com", PASSWORD, first));
		assertThat(second.getValue()).isNotEqualTo(first.getValue());
		mvc.perform(get("/api/me").cookie(first)).andExpect(jsonPath("$.authenticated").value(false));
		mvc.perform(get("/api/me").cookie(second)).andExpect(jsonPath("$.authenticated").value(true));
	}

	// --- passwords --------------------------------------------------------------

	@Test
	void passwordIsStoredAsArgon2idHash() throws Exception {
		register("a@example.com", PASSWORD);
		String hash = jdbc.queryForObject("select password_hash from users where email = 'a@example.com'",
				String.class);
		assertThat(hash).startsWith("$argon2id$").doesNotContain(PASSWORD);
	}

	@Test
	void registrationValidatesInput() throws Exception {
		assertThat(register("a@example.com", "short").getResponse().getStatus()).isEqualTo(400); // < 10 chars
		assertThat(register("not-an-email", PASSWORD).getResponse().getStatus()).isEqualTo(400);
		mvc.perform(mutating(post("/api/auth/register")).contentType(MediaType.APPLICATION_JSON)
			.content("{\"email\":\"a@example.com\",\"password\":\"" + PASSWORD + "\"}")) // no name
			.andExpect(status().isBadRequest());
		assertThat(jdbc.queryForObject("select count(*) from users", Integer.class)).isZero();
	}

	// --- no user enumeration ----------------------------------------------------

	@Test
	void registeringAnExistingEmailLooksIdenticalAndChangesNothing() throws Exception {
		MvcResult first = register("a@example.com", PASSWORD);
		MvcResult again = register("A@Example.com", "another password 123");

		assertThat(again.getResponse().getStatus()).isEqualTo(first.getResponse().getStatus()).isEqualTo(200);
		assertThat(again.getResponse().getContentAsString()).isEqualTo(first.getResponse().getContentAsString());
		assertThat(jdbc.queryForObject("select count(*) from users", Integer.class)).isEqualTo(1);
		// the original password still works, the second one does not
		assertThat(login("a@example.com", PASSWORD).getResponse().getStatus()).isEqualTo(200);
		assertThat(login("a@example.com", "another password 123").getResponse().getStatus()).isEqualTo(401);
	}

	@Test
	void wrongPasswordAndUnknownEmailGetTheSameAnswer() throws Exception {
		register("a@example.com", PASSWORD);
		MvcResult wrongPassword = login("a@example.com", "wrong password 123");
		MvcResult unknownEmail = login("nobody@example.com", "wrong password 123");

		assertThat(wrongPassword.getResponse().getStatus()).isEqualTo(401);
		assertThat(unknownEmail.getResponse().getStatus()).isEqualTo(401);
		assertThat(unknownEmail.getResponse().getContentAsString())
			.isEqualTo(wrongPassword.getResponse().getContentAsString())
			.contains("Invalid email or password");
		assertThat(sessionCookie(wrongPassword)).isNull();
	}

	// --- lockout ----------------------------------------------------------------

	@Test
	void accountLocksAfterTenFailuresEvenForTheRightPassword() throws Exception {
		register("a@example.com", PASSWORD);
		for (int i = 0; i < 10; i++) {
			assertThat(login("a@example.com", "wrong password 123").getResponse().getStatus()).isEqualTo(401);
		}
		MvcResult locked = login("a@example.com", PASSWORD);
		assertThat(locked.getResponse().getStatus()).isEqualTo(401);
		assertThat(locked.getResponse().getContentAsString()).contains("Invalid email or password"); // still generic

		// other accounts are unaffected
		register("b@example.com", PASSWORD);
		assertThat(login("b@example.com", PASSWORD).getResponse().getStatus()).isEqualTo(200);
	}

	// --- CSRF -------------------------------------------------------------------

	@Test
	void stateChangingRequestsNeedTheCsrfHeader() throws Exception {
		String body = json("a@example.com", PASSWORD, "Test User");
		// no token at all
		mvc.perform(post("/api/auth/register").with(freshIp()).contentType(MediaType.APPLICATION_JSON).content(body))
			.andExpect(status().isForbidden());
		// cookie present but header missing (what a cross-site form post would look like)
		Csrf csrf = csrf();
		mvc.perform(post("/api/auth/register").with(freshIp())
			.cookie(csrf.cookie())
			.contentType(MediaType.APPLICATION_JSON)
			.content(body)).andExpect(status().isForbidden());
		// header that does not match the cookie
		mvc.perform(post("/api/auth/register").with(freshIp())
			.cookie(csrf.cookie())
			.header("X-XSRF-TOKEN", "forged")
			.contentType(MediaType.APPLICATION_JSON)
			.content(body)).andExpect(status().isForbidden());
		assertThat(jdbc.queryForObject("select count(*) from users", Integer.class)).isZero();

		// cookie + matching header works
		mvc.perform(post("/api/auth/register").with(freshIp())
			.cookie(csrf.cookie())
			.header("X-XSRF-TOKEN", csrf.token())
			.contentType(MediaType.APPLICATION_JSON)
			.content(body)).andExpect(status().isOk());
	}

	@Test
	void logoutWithoutCsrfTokenIsRejected() throws Exception {
		Cookie session = registerAndLogin("a@example.com");
		mvc.perform(post("/api/auth/logout").cookie(session)).andExpect(status().isForbidden());
		mvc.perform(get("/api/me").cookie(session)).andExpect(jsonPath("$.authenticated").value(true));
	}

	@Test
	void csrfCookieIsReadableByScriptButSessionCookieIsNot() throws Exception {
		MvcResult result = mvc.perform(get("/api/csrf").with(freshIp())).andReturn();
		assertThat(setCookieHeader(result, "XSRF-TOKEN")).doesNotContain("HttpOnly").contains("Path=/");
	}

	// --- rate limiting ----------------------------------------------------------

	@Test
	void loginIsLimitedToFivePerMinutePerIp() throws Exception {
		Csrf csrf = csrf();
		for (int i = 1; i <= 6; i++) {
			MvcResult result = mvc
				.perform(post("/api/auth/login").with(ip("203.0.113.7"))
					.cookie(csrf.cookie())
					.header("X-XSRF-TOKEN", csrf.token())
					.contentType(MediaType.APPLICATION_JSON)
					.content(json("nobody@example.com", "wrong password 123", null)))
				.andReturn();
			assertThat(result.getResponse().getStatus()).as("attempt %d", i).isEqualTo(i <= 5 ? 401 : 429);
			if (i == 6) {
				assertThat(result.getResponse().getHeader("Retry-After")).isNotNull();
			}
		}
		// a different IP is not affected
		assertThat(login("nobody@example.com", "wrong password 123").getResponse().getStatus()).isEqualTo(401);
	}

	@Test
	void searchIsLimitedToSixtyPerMinutePerIp() throws Exception {
		for (int i = 1; i <= 60; i++) {
			mvc.perform(get("/api/jobs").with(ip("203.0.113.8"))).andExpect(status().isOk());
		}
		mvc.perform(get("/api/jobs").with(ip("203.0.113.8"))).andExpect(status().isTooManyRequests());
	}

	@Test
	void forwardedClientIpIsOnlyTrustedWithTheProxySecret() throws Exception {
		// same socket address, different real users behind the frontend: separate buckets
		for (int user = 1; user <= 2; user++) {
			for (int i = 1; i <= 60; i++) {
				mvc.perform(get("/api/jobs").with(ip("198.51.100.1"))
					.header("X-Proxy-Secret", "test-proxy-secret")
					.header("X-Client-IP", "192.0.2." + user)).andExpect(status().isOk());
			}
		}
		mvc.perform(get("/api/jobs").with(ip("198.51.100.1"))
			.header("X-Proxy-Secret", "test-proxy-secret")
			.header("X-Client-IP", "192.0.2.1")).andExpect(status().isTooManyRequests());

		// without the secret, a spoofed header cannot buy a fresh bucket
		for (int i = 1; i <= 60; i++) {
			mvc.perform(get("/api/jobs").with(ip("198.51.100.2")).header("X-Client-IP", "192.0.2." + i)
				.header("X-Proxy-Secret", "wrong")).andExpect(status().isOk());
		}
		mvc.perform(get("/api/jobs").with(ip("198.51.100.2")).header("X-Client-IP", "192.0.2.200"))
			.andExpect(status().isTooManyRequests());
	}

	// --- headers, CORS, default deny ----------------------------------------------

	@Test
	void securityHeadersArePresent() throws Exception {
		mvc.perform(get("https://localhost/api/meta").secure(true))
			.andExpect(header().string("Content-Security-Policy",
					org.hamcrest.Matchers.allOf(org.hamcrest.Matchers.containsString("default-src 'none'"),
							org.hamcrest.Matchers.containsString("frame-ancestors 'none'"))))
			.andExpect(header().string("X-Content-Type-Options", "nosniff"))
			.andExpect(header().string("X-Frame-Options", "DENY"))
			.andExpect(header().string("Referrer-Policy", "strict-origin-when-cross-origin"))
			.andExpect(header().string("Strict-Transport-Security",
					org.hamcrest.Matchers.containsString("max-age=31536000")));
	}

	@Test
	void corsIsNotEnabled() throws Exception {
		mvc.perform(get("/api/meta").header("Origin", "https://evil.example"))
			.andExpect(header().doesNotExist("Access-Control-Allow-Origin"));
		MvcResult preflight = mvc
			.perform(options("/api/auth/login").header("Origin", "https://evil.example")
				.header("Access-Control-Request-Method", "POST"))
			.andReturn();
		assertThat(preflight.getResponse().getHeader("Access-Control-Allow-Origin")).isNull();
		assertThat(preflight.getResponse().getStatus()).isGreaterThanOrEqualTo(400);
	}

	@Test
	void unknownPathsAreDeniedAndUserEndpointsNeedLogin() throws Exception {
		mvc.perform(get("/api/admin/anything")).andExpect(status().isUnauthorized());
		mvc.perform(get("/actuator/env")).andExpect(status().isUnauthorized());
		mvc.perform(get("/api/me/saved")).andExpect(status().isUnauthorized());
		mvc.perform(get("/actuator/health")).andExpect(status().isOk());
	}

	// --- Google account linking ---------------------------------------------------

	@Test
	void googleLoginLinksByVerifiedEmailAndDropsAnUnverifiedPassword() throws Exception {
		// someone registered the address with a password but never proved they own it
		register("victim@example.com", "attacker chose this");
		User linked = userService.upsertGoogleUser("google-sub-1", "Victim@Example.com", "Real Owner");

		assertThat(userRepository.count()).isEqualTo(1);
		assertThat(linked.getProvider()).isEqualTo("google");
		assertThat(linked.isEmailVerified()).isTrue();
		assertThat(linked.getPasswordHash()).isNull();
		assertThat(login("victim@example.com", "attacker chose this").getResponse().getStatus()).isEqualTo(401);
		// second Google login finds the same account by subject
		assertThat(userService.upsertGoogleUser("google-sub-1", "victim@example.com", "Real Owner").getId())
			.isEqualTo(linked.getId());
	}
}
