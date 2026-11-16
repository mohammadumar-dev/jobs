package dev.mushaikh.jobs.user;

import java.time.Instant;
import java.util.UUID;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Entity
@Table(name = "users")
@Getter
@Setter
@NoArgsConstructor
public class User {

	public static final String PROVIDER_LOCAL = "local";
	public static final String PROVIDER_GOOGLE = "google";

	@Id
	@GeneratedValue(strategy = GenerationType.UUID)
	private UUID id;

	@Column(nullable = false, unique = true)
	private String email;

	/** Null for accounts that can only sign in with Google. */
	@Column(name = "password_hash")
	private String passwordHash;

	@Column(nullable = false)
	private String name;

	@Column(nullable = false)
	private String provider = PROVIDER_LOCAL;

	@Column(name = "provider_id")
	private String providerId;

	@Column(name = "email_verified", nullable = false)
	private boolean emailVerified;

	@Column(name = "created_at", nullable = false, updatable = false)
	private Instant createdAt = Instant.now();
}
