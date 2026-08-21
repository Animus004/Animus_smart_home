package com.animus.smartroom.context

/**
 * Single source of truth for the user's home location context.
 */
data class HomeLocation(
    val city: String = "Kalyani",
    val state: String = "West Bengal",
    val country: String = "India",
    val postalCode: String = "741235",
    val timeZone: String = "Asia/Kolkata"
) {
    override fun toString(): String {
        return "$city, $state, $country ($postalCode)"
    }
}

object HomeLocationContext {
    private var currentLocation: HomeLocation = HomeLocation()

    fun getLocation(): HomeLocation = currentLocation

    fun updateLocation(location: HomeLocation) {
        currentLocation = location
    }
}
