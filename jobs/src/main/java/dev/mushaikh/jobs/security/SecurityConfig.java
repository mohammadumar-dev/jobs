package dev.mushaikh.jobs.security;

import org.springframework.beans.factory.ObjectProvider;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.security.config.Customizer;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configurers.AbstractHttpConfigurer;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.core.userdetails.UsernameNotFoundException;
import org.springframework.security.crypto.argon2.Argon2PasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.oauth2.client.registration.ClientRegistrationRepository;
import org.springframework.security.oauth2.client.web.DefaultOAuth2AuthorizationRequestResolver;
import org.springframework.security.oauth2.client.web.OAuth2AuthorizationRequestCustomizers;
import org.springframework.security.oauth2.client.web.OAuth2AuthorizationRequestRedirectFilter;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.HttpStatusEntryPoint;
import org.springframework.security.web.authentication.logout.HttpStatusReturningLogoutSuccessHandler;
import org.springframework.security.web.context.HttpSessionSecurityContextRepository;
import org.springframework.security.web.context.SecurityContextRepository;
import org.springframework.security.web.csrf.CookieCsrfTokenRepository;
import org.springframework.security.web.csrf.CsrfTokenRepository;
import org.springframework.security.web.header.writers.ReferrerPolicyHeaderWriter.ReferrerPolicy;
import org.springframework.security.web.servlet.util.matcher.PathPatternRequestMatcher;
import org.springframework.security.web.util.matcher.NegatedRequestMatcher;
import org.springframework.session.web.http.CookieSerializer;
import org.springframework.session.web.http.DefaultCookieSerializer;

import dev.mushaikh.jobs.config.AppProperties;

@Configuration
public class SecurityConfig {

	@Bean
	PasswordEncoder passwordEncoder() {
		return Argon2PasswordEncoder.defaultsForSpringSecurity_v5_8(); // Argon2id
	}

	@Bean
	SecurityContextRepository securityContextRepository() {
		return new HttpSessionSecurityContextRepository();
	}

	/**
	 * The session cookie, set explicitly rather than through server.servlet.session.cookie.*
	 * so the attributes are identical on every server and are covered by tests:
	 * HttpOnly, Secure, SameSite=Lax, host-only (no Domain) with Path=/ as the
	 * __Host- prefix requires.
	 */
	@Bean
	CookieSerializer cookieSerializer(AppProperties props) {
		DefaultCookieSerializer serializer = new DefaultCookieSerializer();
		serializer.setCookieName(props.sessionCookie().name());
		serializer.setUseHttpOnlyCookie(true);
		serializer.setUseSecureCookie(props.sessionCookie().secure());
		serializer.setSameSite("Lax");
		serializer.setCookiePath("/");
		serializer.setCookieMaxAge((int) props.sessionCookie().maxAge().toSeconds());
		return serializer;
	}

	/** XSRF-TOKEN cookie (JS-readable by design) echoed back in the X-XSRF-TOKEN header. */
	@Bean
	CsrfTokenRepository csrfTokenRepository() {
		CookieCsrfTokenRepository repository = CookieCsrfTokenRepository.withHttpOnlyFalse();
		repository.setCookiePath("/");
		repository.setCookieCustomizer(cookie -> cookie.sameSite("Lax"));
		return repository;
	}

	/**
	 * We authenticate in {@code AuthController}; this bean only stops Spring Boot from
	 * creating its default in-memory user with a generated password.
	 */
	@Bean
	UserDetailsService userDetailsService() {
		return username -> {
			throw new UsernameNotFoundException("not used");
		};
	}

	@Bean
	SecurityFilterChain securityFilterChain(HttpSecurity http, AppProperties props,
			SecurityContextRepository contextRepository, CsrfTokenRepository csrfTokenRepository,
			ObjectProvider<ClientRegistrationRepository> clientRegistrations,
			GoogleLoginSuccessHandler googleSuccessHandler) throws Exception {

		http.securityContext(context -> context.securityContextRepository(contextRepository));

		http.authorizeHttpRequests(auth -> auth
			.requestMatchers("/actuator/health", "/actuator/health/**").permitAll()
			.requestMatchers(HttpMethod.GET, "/api/jobs", "/api/jobs/*", "/api/meta", "/api/meta/tagging", "/api/meta/runs", "/api/me", "/api/csrf").permitAll()
			.requestMatchers(HttpMethod.POST, "/api/auth/register", "/api/auth/login", "/api/auth/logout").permitAll()
			.requestMatchers(HttpMethod.POST, "/api/jobs/*/apply").permitAll()
			.requestMatchers("/oauth2/**", "/login/oauth2/**").permitAll()
			.requestMatchers("/api/me/**").authenticated()
			.requestMatchers("/api/jobs/*/save").authenticated()
			.anyRequest().denyAll());

		// CSRF stays ON. SPA mode: token in the XSRF-TOKEN cookie, sent back as X-XSRF-TOKEN.
		http.csrf(csrf -> csrf.spa().csrfTokenRepository(csrfTokenRepository));

		// Same-origin only (the browser talks to /api on the frontend origin): no CORS at all.
		http.cors(AbstractHttpConfigurer::disable);

		http.formLogin(AbstractHttpConfigurer::disable);
		http.httpBasic(AbstractHttpConfigurer::disable);
		http.requestCache(AbstractHttpConfigurer::disable);
		http.exceptionHandling(ex -> ex.authenticationEntryPoint(new HttpStatusEntryPoint(HttpStatus.UNAUTHORIZED)));

		http.logout(logout -> logout.logoutUrl("/api/auth/logout")
			.invalidateHttpSession(true)
			.clearAuthentication(true)
			.logoutSuccessHandler(new HttpStatusReturningLogoutSuccessHandler(HttpStatus.NO_CONTENT)));

		http.headers(headers -> headers
			.contentSecurityPolicy(csp -> csp
				.policyDirectives("default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"))
			.frameOptions(frame -> frame.deny())
			.contentTypeOptions(Customizer.withDefaults())
			.referrerPolicy(referrer -> referrer.policy(ReferrerPolicy.STRICT_ORIGIN_WHEN_CROSS_ORIGIN))
			.httpStrictTransportSecurity(hsts -> hsts.includeSubDomains(true).maxAgeInSeconds(31_536_000)));

		if (props.security().requireHttps()) {
			// http -> https everywhere except the platform health probe, which arrives
			// over plain http from inside the host network.
			http.redirectToHttps(https -> https.requestMatchers(new NegatedRequestMatcher(
					PathPatternRequestMatcher.withDefaults().matcher("/actuator/health/**"))));
		}

		ClientRegistrationRepository registrations = clientRegistrations.getIfAvailable();
		if (registrations != null) {
			DefaultOAuth2AuthorizationRequestResolver resolver = new DefaultOAuth2AuthorizationRequestResolver(
					registrations, OAuth2AuthorizationRequestRedirectFilter.DEFAULT_AUTHORIZATION_REQUEST_BASE_URI);
			resolver.setAuthorizationRequestCustomizer(OAuth2AuthorizationRequestCustomizers.withPkce());
			String origin = props.publicOrigin();
			http.oauth2Login(oauth -> oauth
				.authorizationEndpoint(endpoint -> endpoint.authorizationRequestResolver(resolver))
				.successHandler(googleSuccessHandler)
				.failureHandler((request, response, exception) -> response.sendRedirect(origin + "/login?error=oauth")));
		}

		return http.build();
	}
}
