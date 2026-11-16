package dev.mushaikh.jobs.user;

import java.util.Locale;
import java.util.Optional;

import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import dev.mushaikh.jobs.security.LoginAttemptService;

@Service
public class UserService {

	private final UserRepository users;
	private final PasswordEncoder encoder;
	private final LoginAttemptService attempts;
	/** Hashed once so a login for an unknown email costs the same as a real one. */
	private final String dummyHash;

	public UserService(UserRepository users, PasswordEncoder encoder, LoginAttemptService attempts) {
		this.users = users;
		this.encoder = encoder;
		this.attempts = attempts;
		this.dummyHash = encoder.encode("timing-equalisation-only");
	}

	public static String normalizeEmail(String email) {
		return email == null ? "" : email.trim().toLowerCase(Locale.ROOT);
	}

	/**
	 * Creates a local account. If the email is already registered nothing changes and
	 * nothing is revealed: the caller answers identically in both cases.
	 */
	@Transactional
	public void register(String rawEmail, String password, String name) {
		String email = normalizeEmail(rawEmail);
		String hash = encoder.encode(password); // always hash: equal work on both paths
		if (users.existsByEmail(email)) {
			return;
		}
		User user = new User();
		user.setEmail(email);
		user.setPasswordHash(hash);
		user.setName(name.trim());
		users.save(user);
	}

	/** Empty for a wrong password, an unknown email, a Google-only account or a locked account. */
	@Transactional(readOnly = true)
	public Optional<User> authenticate(String rawEmail, String password) {
		String email = normalizeEmail(rawEmail);
		Optional<User> user = users.findByEmail(email);
		String hash = user.map(User::getPasswordHash).orElse(null);
		boolean matches = encoder.matches(password, hash != null ? hash : dummyHash);
		if (attempts.isLocked(email)) {
			return Optional.empty(); // even a correct password is refused while locked
		}
		if (!matches || hash == null) {
			attempts.recordFailure(email);
			return Optional.empty();
		}
		attempts.reset(email);
		return user;
	}

	/**
	 * Finds or creates the account for a Google sign-in. Only call with an email Google
	 * reports as verified.
	 */
	@Transactional
	public User upsertGoogleUser(String subject, String rawEmail, String name) {
		String email = normalizeEmail(rawEmail);
		Optional<User> linked = users.findByProviderAndProviderId(User.PROVIDER_GOOGLE, subject);
		if (linked.isPresent()) {
			return linked.get();
		}
		User user = users.findByEmail(email).orElse(null);
		if (user == null) {
			user = new User();
			user.setEmail(email);
			user.setName(name == null || name.isBlank() ? email : name.trim());
		}
		else if (!user.isEmailVerified()) {
			// The address was registered with a password but never proven. Whoever set
			// that password may not own the mailbox, so it must not survive the link.
			user.setPasswordHash(null);
		}
		user.setProvider(User.PROVIDER_GOOGLE);
		user.setProviderId(subject);
		user.setEmailVerified(true);
		return users.save(user);
	}
}
