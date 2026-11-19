# Build
FROM amazoncorretto:25 AS build
# The minimal Amazon Linux base has no tar/gzip; the Maven wrapper needs them.
RUN yum install -y tar gzip && yum clean all
WORKDIR /src
COPY .mvn .mvn
COPY mvnw pom.xml ./
RUN chmod +x mvnw && ./mvnw -q -B dependency:go-offline
COPY src src
RUN ./mvnw -q -B -DskipTests package

# Run (non-root)
FROM amazoncorretto:25
RUN yum install -y shadow-utils && useradd --system --uid 10001 app && yum clean all
USER app
WORKDIR /app
COPY --from=build /src/target/jobs-0.0.1-SNAPSHOT.jar app.jar
ENV JAVA_TOOL_OPTIONS="-XX:MaxRAMPercentage=75 -Duser.timezone=UTC"
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]
