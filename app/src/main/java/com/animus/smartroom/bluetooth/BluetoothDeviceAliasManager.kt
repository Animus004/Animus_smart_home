package com.animus.smartroom.bluetooth

import android.content.Context
import android.content.SharedPreferences

class BluetoothDeviceAliasManager(context: Context) {

    companion object {
        private const val PREFS_NAME = "animus_bluetooth_aliases"
        private const val KEY_PREFIX_ALIAS = "alias_"
    }

    private val prefs: SharedPreferences =
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    fun getAlias(macAddress: String): String? {
        val cleanMac = macAddress.uppercase().trim()
        val alias = prefs.getString(KEY_PREFIX_ALIAS + cleanMac, null)?.trim()
        return if (alias.isNullOrBlank()) null else alias
    }

    fun setAlias(macAddress: String, alias: String?) {
        val cleanMac = macAddress.uppercase().trim()
        val cleanAlias = alias?.trim()
        if (cleanAlias.isNullOrBlank()) {
            removeAlias(cleanMac)
        } else {
            prefs.edit().putString(KEY_PREFIX_ALIAS + cleanMac, cleanAlias).apply()
        }
    }

    fun removeAlias(macAddress: String) {
        val cleanMac = macAddress.uppercase().trim()
        prefs.edit().remove(KEY_PREFIX_ALIAS + cleanMac).apply()
    }

    fun getAllAliases(): Map<String, String> {
        val result = mutableMapOf<String, String>()
        for ((key, value) in prefs.all) {
            if (key.startsWith(KEY_PREFIX_ALIAS) && value is String && value.isNotBlank()) {
                val mac = key.removePrefix(KEY_PREFIX_ALIAS)
                result[mac] = value
            }
        }
        return result
    }
}
