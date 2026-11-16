package dev.mushaikh.jobs.security;

import java.io.IOException;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.oauth2.core.oidc.user.OidcUser;
import org.springframework.security.web.authentication.AuthenticationSuccessHandler;
import org.springframework.stereotype.Component;

import dev.mushaikh.jobs.config.AppProperties;
import dev.mushaikh.jobs.user.User;
import dev.mushaikh.jobs.user.UserService;

/**
 * After Google has authenticated the user: require a verified email, find or link
 * the local account, and replace the OAuth2 authentication with our own small
 * session principal (no Google tokens are kept in the session).
 */
@Component
public class GoogleLoginSuccessHandler implements AuthenticationSuccessHandler {

	private final UserService users;
	private final SessionLogin sessionLogin;
	private final String origin;

	public GoogleLoginSuccessHandler(UserService users, SessionLogin sessionLogin, AppProperties props) {
		this.users = users;
		this.sessionLogin = sessionLogin;
		this.origin = props.publicOrigin();
	}

	@Override
	public void onAuthenticationSuccess(HttpServletRequest request, HttpServletResponse response,
			Authentication authentication) throws IOException {
		if (!(authentication.getPrincipal() instanceof OidcUser oidc) || !Boolean.TRUE.equals(oidc.getEmailVerified())
				|| oidc.getEmail() == null) {
			SecurityContextHolder.clearContext();
			if (request.getSession(false) != null) {
				request.getSession(false).invalidate();
			}
			response.sendRedirect(origin + "/login?error=oauth");
			return;
		}
		User user = users.upsertGoogleUser(oidc.getSubject(), oidc.getEmail(), oidc.getFullName());
		sessionLogin.establish(AppPrincipal.of(user), request, response);
		response.sendRedirect(origin + "/dashboard");
	}
}
