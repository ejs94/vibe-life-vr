package su.xash.engine.ui.diagnostics

import android.os.Build
import android.os.Bundle
import android.os.Environment
import androidx.navigation.fragment.findNavController
import androidx.preference.Preference
import androidx.preference.PreferenceCategory
import androidx.preference.PreferenceFragmentCompat
import su.xash.engine.R
import su.xash.engine.util.CrashReports

class DiagnosticsFragment : PreferenceFragmentCompat() {
	override fun onCreatePreferences(savedInstanceState: Bundle?, rootKey: String?) {
		val ctx = requireContext()
		preferenceScreen = preferenceManager.createPreferenceScreen(ctx)

		// System & Headset Info
		val sysCategory = PreferenceCategory(ctx).apply {
			title = "Meta Quest System & Runtime"
		}
		preferenceScreen.addPreference(sysCategory)

		sysCategory.addPreference(Preference(ctx).apply {
			title = "Device Model"
			summary = "${Build.MANUFACTURER.uppercase()} ${Build.MODEL} (Android ${Build.VERSION.RELEASE}, API ${Build.VERSION.SDK_INT})"
			isSelectable = false
		})

		sysCategory.addPreference(Preference(ctx).apply {
			title = "OpenXR Runtime"
			summary = getString(R.string.openxr_status_ready)
			isSelectable = false
		})

		// Storage & Permissions
		val storageCategory = PreferenceCategory(ctx).apply {
			title = "Storage & Paths"
		}
		preferenceScreen.addPreference(storageCategory)

		val isStorageGranted = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
			Environment.isExternalStorageManager()
		} else {
			true
		}

		storageCategory.addPreference(Preference(ctx).apply {
			title = "Game Directory"
			summary = "${Environment.getExternalStorageDirectory().absolutePath}/xash"
			isSelectable = false
		})

		storageCategory.addPreference(Preference(ctx).apply {
			title = "All-Files Permission"
			summary = if (isStorageGranted) "Active (Granted)" else "Not Granted"
			isSelectable = false
		})

		// Logs
		val logsCategory = PreferenceCategory(ctx).apply {
			title = "Diagnostics & Crash Logs"
		}
		preferenceScreen.addPreference(logsCategory)

		val crashCount = CrashReports.historyDir(ctx).listFiles()?.count { it.isDirectory } ?: 0
		logsCategory.addPreference(Preference(ctx).apply {
			title = getString(R.string.crash_logs)
			summary = "$crashCount recorded log(s)"
			setOnPreferenceClickListener {
				findNavController().navigate(R.id.action_diagnosticsFragment_to_crashLogsFragment)
				true
			}
		})
	}
}
