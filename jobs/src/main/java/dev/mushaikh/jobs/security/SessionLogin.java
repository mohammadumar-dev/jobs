package dev.mushaikh.jobs.security;

import java.util.List;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContext;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.web.authentication.session.ChangeSessionIdAuthenticationStrategy;
import org.springframework.security.web.authentication.session.CompositeSessionAuthenticationStrategy;
import org.springframework.security.web.authentication.session.SessionAuthenticationStrategy;
import org.springframework.security.web.context.SecurityContextRepository;
import org.springframework.security.web.csrf.CsrfAuthenticationStrategy;
import org.springframework.security.web.csrf.CsrfTokenRepository;
import org.springframework.stereotype.Component;

/**
 * Turns a verified user into a logged-in session. Used by both the password login
 * and the Google login so they behave identically: the session id is rotated
 * (session fixation), the CSRF token is rotated, and only an {@link AppPrincipal}
 * is stored server-side.
 */
@Component
public class SessionLogin {

	private static final List<SimpleGrantedAuthority> AUTHORITIES = List.of(new SimpleGrantedAuthority("ROLE_USER"));

	private final SecurityContextRepository contextRepository;
	private final SessionAuthenticationStrategy sessionStrategy;

	public SessionLogin(SecurityContextRepository contextRepository, CsrfTokenRepository csrfTokenRepository) {
		this.contextRepository = contextRepository;
		this.sessionStrategy = new CompositeSessionAuthenticationStrategy(
				List.of(new ChangeSessionIdAuthenticationStrategy(), new CsrfAuthenticationStrategy(csrfTokenRepository)));
	}

	public void establish(AppPrincipal principal, HttpServletRequest request, HttpServletResponse response) {
		Authentication auth = UsernamePasswordAuthenticationToken.authenticated(principal, null, AUTHORITIES);
		sessionStrategy.onAuthentication(auth, request, response);
		SecurityContext context = SecurityContextHolder.createEmptyContext();
		context.setAuthentication(auth);
		SecurityContextHolder.setContext(context);
		contextRepository.saveContext(context, request, response);
	}
}
