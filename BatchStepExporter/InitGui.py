import FreeCADGui as Gui


class BatchStepExporterWorkbench(Gui.Workbench):
    MenuText = "Batch STEP Exporter"
    ToolTip = "Iterative parameter recompute + STEP export for all bodies"
    Icon = ""

    def Initialize(self):
        import importlib
        import traceback

        import FreeCAD as App

        try:
            impl = importlib.import_module("batch_step_exporter")
        except Exception as exc:
            App.Console.PrintError(
                "BatchStepExporter: Fehler beim Laden von batch_step_exporter: %s\n" % str(exc)
            )
            App.Console.PrintError(traceback.format_exc())
            return

        impl.register_command()
        self.appendToolbar("Batch STEP Exporter", ["BatchStepExport"])
        self.appendMenu("Batch STEP Exporter", ["BatchStepExport"])

    def GetClassName(self):
        return "Gui::PythonWorkbench"


Gui.addWorkbench(BatchStepExporterWorkbench())
