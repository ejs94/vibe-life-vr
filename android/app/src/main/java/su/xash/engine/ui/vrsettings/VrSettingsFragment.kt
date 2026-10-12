package su.xash.engine.ui.vrsettings

import android.os.Bundle
import androidx.preference.PreferenceFragmentCompat
import su.xash.engine.R

class VrSettingsFragment : PreferenceFragmentCompat() {
	override fun onCreatePreferences(savedInstanceState: Bundle?, rootKey: String?) {
		preferenceManager.sharedPreferencesName = "vr_preferences"
		setPreferencesFromResource(R.xml.vr_preferences, rootKey)
	}
}
