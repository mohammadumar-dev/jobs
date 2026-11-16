package dev.mushaikh.jobs;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.hamcrest.Matchers;
import org.junit.jupiter.api.Test;

import org.springframework.test.context.TestPropertySource;

/** Production setting: plain http is redirected to https. */
@TestPropertySource(properties = "app.security.require-https=true")
class HttpsRedirectTests extends ApiTestBase {

	@Test
	void httpIsRedirectedToHttps() throws Exception {
		mvc.perform(get("/api/meta"))
			.andExpect(status().is3xxRedirection())
			.andExpect(header().string("Location", Matchers.startsWith("https://")));
		mvc.perform(get("https://localhost/api/meta").secure(true)).andExpect(status().isOk());
	}

	@Test
	void healthProbeIsExemptFromTheRedirect() throws Exception {
		mvc.perform(get("/actuator/health")).andExpect(status().isOk());
	}
}
