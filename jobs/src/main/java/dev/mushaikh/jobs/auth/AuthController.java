package dev.mushaikh.jobs.auth;

import java.util.Map;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ProblemDetail;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.web.csrf.CsrfToken;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import dev.mushaikh.jobs.security.AppPrincipal;
import dev.mushaikh.jobs.security.SessionLogin;
import dev.mushaikh.jobs.user.UserService;

@RestController
@RequestMapping("/api")
public class AuthController {

	static final String REGISTER_MESSAGE = "If this email is not registered yet, your account is ready. Please sign in.";
	static final String LOGIN_FAILED = "Invalid email or password.";

	public record RegisterRequest(@NotBlank @Email @Size(max = 254) String email,
			@NotBlank @Size(min = 10, max = 128) String password, @NotBlank @Size(max = 80) String name) {
	}

	public record LoginRequest(@NotBlank @Email @Size(max = 254) String email,
			@NotBlank @Size(max = 128) String password) {
	}

	public record MeResponse(boolean authenticated, String email, String name) {

		static MeResponse of(AppPrincipal principal) {
			return principal == null ? new MeResponse(false, null, null)
					: new MeResponse(true, principal.email(), principal.displayName());
		}
	}

	private final UserService users;
	private final SessionLogin sessionLogin;

	public AuthController(UserService users, SessionLogin sessionLogin) {
		this.users = users;
		this.sessionLogin = sessionLogin;
	}

	/** Same status and body whether or not the email was already registered. */
	@PostMapping("/auth/register")
	public Map<String, String> register(@Valid @RequestBody RegisterRequest request) {
		try {
			users.register(request.email(), request.password(), request.name());
		}
		catch (DataIntegrityViolationException ignored) {
			// two concurrent registrations for one email: the other one won
		}
		return Map.of("message", REGISTER_MESSAGE);
	}

	@PostMapping("/auth/login")
	public ResponseEntity<?> login(@Valid @RequestBody LoginRequest request, HttpServletRequest http,
			HttpServletResponse response) {
		return users.authenticate(request.email(), request.password()).<ResponseEntity<?>>map(user -> {
			AppPrincipal principal = AppPrincipal.of(user);
			sessionLogin.establish(principal, http, response);
			return ResponseEntity.ok(MeResponse.of(principal));
		}).orElseGet(() -> ResponseEntity.status(HttpStatus.UNAUTHORIZED)
			.body(ProblemDetail.forStatusAndDetail(HttpStatus.UNAUTHORIZED, LOGIN_FAILED)));
	}

	@GetMapping("/me")
	public MeResponse me(@AuthenticationPrincipal AppPrincipal principal) {
		return MeResponse.of(principal);
	}

	/** Touching the token makes Spring Security set the XSRF-TOKEN cookie. */
	@GetMapping("/csrf")
	public Map<String, String> csrf(CsrfToken token) {
		return Map.of("headerName", token.getHeaderName());
	}
}
