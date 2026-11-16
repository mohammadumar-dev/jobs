package dev.mushaikh.jobs.security;

import java.io.Serializable;
import java.security.Principal;
import java.util.UUID;

import dev.mushaikh.jobs.user.User;

/** The only thing kept in the session about the signed-in user. */
public record AppPrincipal(UUID id, String email, String displayName) implements Principal, Serializable {

	public static AppPrincipal of(User user) {
		return new AppPrincipal(user.getId(), user.getEmail(), user.getName());
	}

	@Override
	public String getName() {
		return id.toString();
	}
}
