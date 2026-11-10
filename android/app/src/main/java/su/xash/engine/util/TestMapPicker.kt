package su.xash.engine.util

import android.content.Context
import android.view.LayoutInflater
import android.view.View
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import su.xash.engine.R

/** Explicit map picker used by the library card. */
object TestMapPicker {
	fun show(ctx: Context, onPick: (String) -> Unit) {
		val view = LayoutInflater.from(ctx).inflate(R.layout.dialog_test_maps, null)
		val dialog = MaterialAlertDialogBuilder(ctx)
			.setView(view)
			.setNegativeButton(android.R.string.cancel, null)
			.create()

		fun bind(id: Int, args: String) {
			view.findViewById<View>(id).setOnClickListener {
				dialog.dismiss()
				onPick(args)
			}
		}

		bind(R.id.cardCrossfire, TestMaps.CROSSFIRE)
		bind(R.id.cardTestbed, TestMaps.TESTBED)
		bind(R.id.cardHazard, TestMaps.HAZARD)

		dialog.show()
	}
}
