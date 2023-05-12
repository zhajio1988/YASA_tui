from textual.app import App, ComposeResult
from textual.widgets import Label, RadioButton, RadioSet, TabbedContent, TabPane
from textual.reactive import reactive
from textual.widgets import Footer, Header, Static, DataTable, ProgressBar
from rich.text import Text, TextType

import logging
import sqlite3
import clipboard as cp

logging.basicConfig(level=logging.DEBUG,
                    filename='tui.log',
                    filemode='a',
                    format='%(asctime)s - %(pathname)s[line:%(lineno)d] - %(levelname)s: %(message)s'
                    )
userList = ["jiongz", "pengfeia", "mingxiangs", "yunfengl", "taoc", "ziwent", "kaiwenz"]
RegrCaseStatusROWS = [
    ("CaseName", "Msg", "SimTime", "LogFile"),
]

RegrCmdROWS = [
    ("SampleTime", "PICOsimCmd"),
]

class RegrSummary(Static):
    """A widget to display regression status."""
    passed = reactive(0)
    failed = reactive(0)
    warning = reactive(0)
    total = reactive(0)

    def compose(self) -> ComposeResult:
        """Create child widgets of a RegrSummary."""
        yield ProgressBar(show_eta=False)

    def on_mount(self) -> None:
        """Event handler called when widget is added to the app."""
        self.preDisplayCnt = 0
        self.progCnt = 0
        self.update_timer = self.set_interval(1, self.update_progress)

    def update_progress(self) -> None:
        """Method to update regression status to current."""
        conn = sqlite3.connect('db/%s_results.db' % self.name)
        c = conn.cursor()
        c.execute("SELECT passed, warned, failed, total FROM regr_%s where Id='%s';" % (self.name, self.id.split("_")[2]))

        rows = c.fetchall()
        if self.progCnt == 0:
            if len(rows) ==0:
                self.query_one(ProgressBar).update(total=100)
            else:
                self.query_one(ProgressBar).update(total=len(rows))
        if self.preDisplayCnt < len(rows):
            self.passed = int(rows[-1][0])
            self.warning = int(rows[-1][1])
            self.failed = int(rows[-1][2])
            self.total = int(rows[-1][3])
            if self.progCnt == 0:
                self.query_one(ProgressBar).update(total=self.total)
                self.progCnt = self.progCnt + 1
            self.preDisplayCnt = len(rows)
            logging.debug("debug point vars0 %s %s %s %s %s" % (self.passed, self.warning, self.failed, self.total, self.preDisplayCnt))

            """Called automatically to advance the progress bar."""
            self.query_one(ProgressBar).advance(self.passed + self.warning + self.failed)

        if (self.passed >0 or self.failed>0) and ((self.passed + self.warning + self.failed) == self.total):
            logging.debug("debug point vars1 %s %s %s %s %s" % (self.passed, self.warning, self.failed, self.total, self.preDisplayCnt))
            logging.debug("debug point stop")
            self.update_timer.pause()
        conn.close()

    def watch_passed(self) -> None:
        """Called when the passed attribute changes."""
        self.update(f"PASS: {self.passed:0d} FAIL: {self.failed:0d} WARNING: {self.warning:0d} TOTAL: {self.total:0d}")

    def watch_failed(self) -> None:
        """Called when the failed attribute changes."""
        self.update(f"PASS: {self.passed:0d} FAIL: {self.failed:0d} WARNING: {self.warning:0d} TOTAL: {self.total:0d}")

class RegrCaseStatus(Static):
    """A RegrCaseStatus widget."""

    def compose(self) -> ComposeResult:
        """Create child widgets of a RegrCaseStatus."""
        #yield RegrSummary()
        yield DataTable(id=self.id)

    def on_mount(self) -> None:
        self.table = self.query_one(DataTable)
        logging.debug(f"debug point table id0 {self.table.id}")
        self.table.focus()
        self.table.add_columns(*RegrCaseStatusROWS[0])
        self.table.zebra_stripes = True
        self.table.cursor_type = "cell"
        self.conn = sqlite3.connect('db/%s_results.db' % self.name)
        self.c = self.conn.cursor()
        res = self.c.execute("SELECT CaseName, Msg, SimTime, LogFile FROM tests_%s where Id='%s'" % (self.name, self.id.split("_")[1]))
        rows = res.fetchall()
        self.preDisplayCnt = len(rows)
        self.table.add_rows(self.style_fail_rows(rows))
        #self.table.action_scroll_end()
        self.update_timer = self.set_interval(1, self.update_time)

    def update_time(self) -> None:
        """Method to update time to current."""
        res = self.c.execute("SELECT CaseName, Msg, SimTime, LogFile FROM tests_%s where Id='%s'" % (self.name, self.id.split("_")[1]))
        rows = res.fetchall()
        if self.preDisplayCnt < len(rows):
            logging.debug("debug point rows %d %d %d" % (self.preDisplayCnt,  len(rows), self.preDisplayCnt-len(rows)))
            self.table.add_rows(self.style_fail_rows(rows[self.preDisplayCnt-len(rows):]))
            self.table.action_scroll_end()
            #for i in range(len(rows)-self.preDisplayCnt-1):
            #    table.action_cursor_down()
            self.preDisplayCnt = len(rows)

    def style_fail_rows(self, rows):
        styled_rows=[]
        for row in rows:
            if row[1] == "fail":
                # Adding styled and justified `Text` objects instead of plain strings.
                styled_row = [
                    Text(str(cell), style="italic #ff0000", justify="left") for cell in row
                ]
            else:
                styled_row = [
                    Text(str(cell), justify="left") for cell in row
                ]
            styled_rows.append(styled_row)
        return styled_rows

    def on_data_table_cell_selected(self, event: DataTable.CellSelected) -> None:
        if self.table.id == event.data_table.id:
            if event.coordinate.column == 3:
                logging.debug("debug point table value %s", self.table.get_cell_at(event.coordinate))
                #copy log path to system clipboard
                cp.copy(f"{self.table.get_cell_at(event.coordinate)}")

class RegrCmd(Static):
    """A RegrCmd widget."""

    def compose(self) -> ComposeResult:
        """Create child widgets of a RegrCmd."""
        yield DataTable()

    def on_mount(self) -> None:
        self.child_id = []
        self.uniq_child_id = []
        self.table = self.query_one(DataTable)
        logging.debug(f"debug point table id1 {self.table.id}")
        self.table_press_cnt = 0
        self.table.add_columns(*RegrCmdROWS[0])
        self.conn = sqlite3.connect('db/cmd.db')
        self.c = self.conn.cursor()
        res = self.c.execute("SELECT sampleTime, PICOsimCmd, id FROM user_%s" % self.name)
        self.rows = res.fetchall()
        self.preDisplayCnt = len(self.rows)
        self.table.add_rows(self.updateList(self.rows)[0:])
        self.table.zebra_stripes = True
        self.table.cursor_type = "cell"
        self.table.focus()
        self.update_timer = self.set_interval(60, self.update_time)

    def update_time(self) -> None:
        """Method to update time to current."""
        res = self.c.execute("SELECT sampleTime, PICOsimCmd, id FROM user_%s" % self.name)
        self.rows = res.fetchall()
        if self.preDisplayCnt < len(self.rows):
            self.table.add_rows(self.updateList(self.rows)[self.preDisplayCnt-len(self.rows):])
            self.table.action_scroll_end()
            #for i in range(len(rows)-self.preDisplayCnt-1):
            #    table.action_cursor_down()
            self.preDisplayCnt = len(self.rows)

    def on_data_table_cell_selected(self, event: DataTable.CellSelected) -> None:
        if self.table.id == event.data_table.id:
            logging.debug("debug point table row0 %s", event.coordinate.row)
            logging.debug("debug point table row1 %s", self.table.cursor_row)
            logging.debug("debug point table row_id %s", self.rows[self.table.cursor_row][2])
            cid = "_".join(["regrCase", self.rows[self.table.cursor_row][2]])
            self.child_id.append(cid)
            if cid in self.child_id:
                cidCnt = self.child_id.count(cid)
                uniqCid = "_".join(["regrCase", self.rows[self.table.cursor_row][2], str(cidCnt)])
            else:
                uniqCid = cid
            self.uniq_child_id.append(uniqCid)

            #self.table.add_class("-resize")
            self.mount(RegrSummary(name=self.name, id="regrSum_" + uniqCid))
            self.mount(RegrCaseStatus(name=self.name, id=uniqCid))

            regrCaseStsCurChild = self.get_child_by_id(uniqCid)
            regrSumCurChild = self.get_child_by_id("regrSum_" + uniqCid)
            self.uniq_child_id.append("regrSum_" + uniqCid)

            regrCaseStsCurChild.add_class("-active")
            regrSumCurChild.add_class("-active")
            if self.table_press_cnt != 0:
                for cid in self.uniq_child_id[:-2]:
                    child = self.get_child_by_id(cid)
                    child.add_class("-deactive")
                    self.move_child(child, after=regrCaseStsCurChild)

            self.table_press_cnt = self.table_press_cnt + 1

    def updateList(self, inList):
        showList = []
        for item in inList:
            showList.append(tuple(list(item)[0:-1]))
        return showList

class YASA_tui(App):
    """An example of tabbed content."""
    CSS_PATH = "YASA_tui.css"

    BINDINGS = []
    
    for user in userList:
        BINDINGS.append((user[0], f"show_tab('{user}')", user))

    def compose(self) -> ComposeResult:
        """Compose app with tabbed content."""
        # Footer to show keys
        yield Footer()
        conn = sqlite3.connect('db/cmd.db')
        c =conn.cursor()
        res = c.execute("select name from sqlite_master where type='table' order by name")
        rows = res.fetchall()
        validUser=[]
        for row in rows:
           validUser.append(row[0].split("_")[1]) 
        # Add the TabbedContent widget
        with TabbedContent(initial="jiongz"):
            for user in userList:
                if user in validUser:
                    with TabPane(user, id=user):
                        yield RegrCmd(name=user, id=user)

    def action_show_tab(self, tab: str) -> None:
        """Switch to a new tab."""
        self.get_child_by_type(TabbedContent).active = tab

if __name__ == "__main__":
    app = YASA_tui()
    app.run()
