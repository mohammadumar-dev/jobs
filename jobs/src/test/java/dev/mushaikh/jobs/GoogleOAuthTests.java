package dev.mushaikh.jobs;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;

import org.junit.jupiter.api.Test;

import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.servlet.MvcResult;

/** Google login is wired as authorization code + PKCE with a state parameter. */
@ActiveProfiles({ "test", "google" })
@TestPropertySource(properties = { "GOOGLE_CLIENT_ID=test-client-id", "GOOGLE_CLIENT_SECRET=test-secret",
		"app.public-origin=https://app.example.com" })
class GoogleOAuthTests extends ApiTestBase {

	@Test
	void authorizationRequestUsesCodeFlowWithPkceAndState() throws Exception {
		MvcResult result = mvc.perform(get("/oauth2/authorization/google"))
			.andExpect(status().is3xxRedirection())
			.andReturn();
		String location = URLDecoder.decode(result.getResponse().getHeader("Location"), StandardCharsets.UTF_8);

		assertThat(location).startsWith("https://accounts.google.com/o/oauth2/v2/auth")
			.contains("response_type=code")
			.contains("client_id=test-client-id")
			.contains("code_challenge=")
			.contains("code_challenge_method=S256")
			.contains("state=")
			.contains("redirect_uri=https://app.example.com/login/oauth2/code/google")
			.doesNotContain("test-secret");
	}

	@Test
	void callbackWithUnknownStateIsRejected() throws Exception {
		MvcResult result = mvc.perform(get("/login/oauth2/code/google").param("code", "abc").param("state", "forged"))
			.andExpect(status().is3xxRedirection())
			.andReturn();
		assertThat(result.getResponse().getHeader("Location")).isEqualTo("https://app.example.com/login?error=oauth");
		assertThat(jdbc.queryForObject("select count(*) from users", Integer.class)).isZero();
	}
}
