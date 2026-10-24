package su.xash.engine

import android.app.Application
import android.content.Context
import android.os.StrictMode

class MainApplication : Application() {
	override fun attachBaseContext(base: Context?) {
		super.attachBaseContext(base)

		if (BuildConfig.DEBUG) {
			// enable strict mode to detect memory leaks etc.
			StrictMode.enableDefaults()
		}
	}
}
