package dev.mushaikh.jobs.security;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Duration;
import java.util.concurrent.TimeUnit;

import com.github.benmanes.caffeine.cache.Cache;
import com.github.benmanes.caffeine.cache.Caffeine;
import io.github.bucket4j.Bucket;
import io.github.bucket4j.ConsumptionProbe;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import dev.mushaikh.jobs.config.AppProperties;

/**
 * Per-IP token buckets (Bucket4j): login/register 5 per minute, job search 60 per
 * minute. Runs before Spring Security so rejected requests cost almost nothing.
 *
 * Client IP: every browser request arrives through the Next.js server, so the socket
 * address is the frontend's, not the user's. The frontend therefore sends the real
 * address in X-Client-IP together with a shared secret in X-Proxy-Secret; without
 * the correct secret the header is ignored and the socket address is used, so a
 * caller hitting the API directly cannot pick its own bucket.
 */
@Component
@Order(Ordered.HIGHEST_PRECEDENCE + 10)
public class RateLimitFilter extends OncePerRequestFilter {

	private final int authPerMinute;
	private final int searchPerMinute;
	private final Cache<String, Bucket> buckets = Caffeine.newBuilder()
		.expireAfterAccess(Duration.ofMinutes(10))
		.maximumSize(200_000)
		.build();

	private final byte[] proxySecret;

	public RateLimitFilter(AppProperties props) {
		String secret = props.proxySecret() == null ? "" : props.proxySecret().strip();
		this.proxySecret = secret.getBytes(StandardCharsets.UTF_8);
		this.authPerMinute = props.rateLimit().authPerMinute();
		this.searchPerMinute = props.rateLimit().searchPerMinute();
	}

	@Override
	protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
			throws ServletException, IOException {
		String path = request.getRequestURI();
		String method = request.getMethod();
		String group;
		int limit;
		if ("POST".equals(method) && (path.equals("/api/auth/login") || path.equals("/api/auth/register"))) {
			group = "auth";
			limit = authPerMinute;
		}
		else if ("GET".equals(method) && (path.equals("/api/jobs") || path.startsWith("/api/jobs/"))) {
			group = "search";
			limit = searchPerMinute;
		}
		else {
			chain.doFilter(request, response);
			return;
		}
		Bucket bucket = buckets.get(group + "|" + clientIp(request), key -> newBucket(limit));
		ConsumptionProbe probe = bucket.tryConsumeAndReturnRemaining(1);
		if (probe.isConsumed()) {
			chain.doFilter(request, response);
			return;
		}
		long retryAfter = Math.max(1, TimeUnit.NANOSECONDS.toSeconds(probe.getNanosToWaitForRefill()));
		response.setStatus(429);
		response.setHeader(HttpHeaders.RETRY_AFTER, Long.toString(retryAfter));
		response.setContentType(MediaType.APPLICATION_PROBLEM_JSON_VALUE);
		response.getWriter().write("{\"status\":429,\"title\":\"Too Many Requests\"}");
	}

	String clientIp(HttpServletRequest request) {
		String presented = request.getHeader("X-Proxy-Secret");
		String forwarded = request.getHeader("X-Client-IP");
		if (proxySecret.length > 0 && presented != null && forwarded != null && !forwarded.isBlank()
				&& forwarded.length() <= 45
				&& MessageDigest.isEqual(proxySecret, presented.getBytes(StandardCharsets.UTF_8))) {
			return forwarded.strip();
		}
		return request.getRemoteAddr();
	}

	private static Bucket newBucket(int perMinute) {
		return Bucket.builder()
			.addLimit(limit -> limit.capacity(perMinute).refillIntervally(perMinute, Duration.ofMinutes(1)))
			.build();
	}
}
