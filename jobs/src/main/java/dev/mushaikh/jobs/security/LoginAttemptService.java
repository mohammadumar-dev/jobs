package dev.mushaikh.jobs.security;

import java.util.concurrent.atomic.AtomicInteger;

import com.github.benmanes.caffeine.cache.Cache;
import com.github.benmanes.caffeine.cache.Caffeine;

import org.springframework.stereotype.Service;

import dev.mushaikh.jobs.config.AppProperties;

/**
 * Account lockout: after N failed logins for an email, refuse logins for that email
 * until the window expires. In-memory, so it is per API instance.
 */
@Service
public class LoginAttemptService {

	private final int maxFailures;
	private final Cache<String, AtomicInteger> failures;

	public LoginAttemptService(AppProperties props) {
		this.maxFailures = props.lockout().maxFailures();
		this.failures = Caffeine.newBuilder()
			.expireAfterWrite(props.lockout().duration())
			.maximumSize(200_000)
			.build();
	}

	public boolean isLocked(String email) {
		AtomicInteger count = failures.getIfPresent(email);
		return count != null && count.get() >= maxFailures;
	}

	public void recordFailure(String email) {
		failures.get(email, key -> new AtomicInteger()).incrementAndGet();
	}

	public void reset(String email) {
		failures.invalidate(email);
	}

	public void clearAll() {
		failures.invalidateAll();
	}
}
