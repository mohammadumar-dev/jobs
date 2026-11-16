package dev.mushaikh.jobs.job;

import java.net.URI;
import java.net.URISyntaxException;
import java.util.Locale;

import org.jsoup.Jsoup;
import org.jsoup.nodes.Document;
import org.jsoup.parser.Parser;
import org.jsoup.safety.Safelist;

/** Defence in depth for text and URLs that originate from third-party job boards. */
public final class TextSafety {

	private static final Document.OutputSettings KEEP_NEWLINES = new Document.OutputSettings().prettyPrint(false);

	private TextSafety() {
	}

	/**
	 * Descriptions are stored as plain text, but they come from outside, so every
	 * response passes through a jsoup allowlist that permits no elements at all. The
	 * result is plain text: clients must render it as text, never as HTML.
	 */
	public static String plainText(String value) {
		if (value == null || value.isEmpty()) {
			return "";
		}
		String stripped = Jsoup.clean(value, "", Safelist.none(), KEEP_NEWLINES);
		return Parser.unescapeEntities(stripped, false).strip();
	}

	/** The URL if it is an absolute http(s) URL with a host, otherwise null. */
	public static String httpUrlOrNull(String value) {
		if (value == null) {
			return null;
		}
		try {
			URI uri = new URI(value.strip());
			String scheme = uri.getScheme() == null ? "" : uri.getScheme().toLowerCase(Locale.ROOT);
			if ((scheme.equals("https") || scheme.equals("http")) && uri.getHost() != null) {
				return uri.toString();
			}
		}
		catch (URISyntaxException ignored) {
			// fall through
		}
		return null;
	}
}
