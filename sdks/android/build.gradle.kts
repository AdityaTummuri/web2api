plugins {
    kotlin("jvm") version "1.9.22"
    `maven-publish`
}

group = "com.web2api"
version = "2.0.0"

repositories {
    mavenCentral()
    google()
}

dependencies {
    // Coroutines & Flow
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.8.0")

    // Modern HTTP networking with SSE support
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("com.squareup.okhttp3:okhttp-sse:4.12.0")

    // JSON serialization
    implementation("com.google.code.gson:gson:2.10.1")

    // Unit Testing
    testImplementation(kotlin("test"))
    testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.8.0")
    testImplementation("com.squareup.okhttp3:mockwebserver:4.12.0")
}

tasks.test {
    useJUnitPlatform()
}

kotlin {
    jvmToolchain(17)
}

publishing {
    publications {
        create<MavenPublication>("mavenJava") {
            from(components["java"])
            groupId = "com.web2api"
            artifactId = "web2api-android"
            version = "2.0.0"
        }
    }
}
