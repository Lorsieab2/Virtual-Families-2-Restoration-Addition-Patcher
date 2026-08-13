using System;
using System.Collections.Generic;
using System.Drawing;
using System.Globalization;
using System.IO;
using System.Text;
using System.Windows.Forms;

namespace VF2NativeRebuild
{
    static class Program
    {
        [STAThread]
        static void Main(string[] args)
        {
            if (args.Length > 0 && args[0] == "--write-sample-save")
            {
                AndroidStyleSampleSave.Write(AppDomain.CurrentDomain.BaseDirectory);
                return;
            }
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new GameForm());
        }
    }

    enum NeedKind { Energy, Fed, Happy, Clean }

    sealed class Person
    {
        public string Name;
        public string Role;
        public float X;
        public float Y;
        public float TargetX;
        public float TargetY;
        public int Energy;
        public int Fed;
        public int Happy;
        public int Clean;
        public string Action;
        public int ActionTicks;
        public Color Shirt;

        public Person(string name, string role, float x, float y, Color shirt)
        {
            Name = name;
            Role = role;
            X = TargetX = x;
            Y = TargetY = y;
            Energy = 76;
            Fed = 74;
            Happy = 70;
            Clean = 78;
            Action = "Wandering";
            ActionTicks = 0;
            Shirt = shirt;
        }

        public int Need(NeedKind kind)
        {
            if (kind == NeedKind.Energy) return Energy;
            if (kind == NeedKind.Fed) return Fed;
            if (kind == NeedKind.Happy) return Happy;
            return Clean;
        }

        public void SetNeed(NeedKind kind, int value)
        {
            value = Math.Max(0, Math.Min(100, value));
            if (kind == NeedKind.Energy) Energy = value;
            else if (kind == NeedKind.Fed) Fed = value;
            else if (kind == NeedKind.Happy) Happy = value;
            else Clean = value;
        }
    }

    sealed class Room
    {
        public string Name;
        public Rectangle Area;
        public Color Fill;
        public Color Accent;

        public Room(string name, Rectangle area, Color fill, Color accent)
        {
            Name = name;
            Area = area;
            Fill = fill;
            Accent = accent;
        }
    }

    sealed class Furniture
    {
        public string Name;
        public Rectangle Area;
        public Color Fill;
        public string Room;
        public NeedKind Need;
        public int Boost;

        public Furniture(string name, Rectangle area, Color fill, string room, NeedKind need, int boost)
        {
            Name = name;
            Area = area;
            Fill = fill;
            Room = room;
            Need = need;
            Boost = boost;
        }
    }

    sealed class GameForm : Form
    {
        readonly Timer timer = new Timer();
        readonly Random rng = new Random();
        readonly List<Person> people = new List<Person>();
        readonly List<Room> rooms = new List<Room>();
        readonly List<Furniture> furniture = new List<Furniture>();
        readonly List<string> log = new List<string>();
        readonly Button feedButton = new Button();
        readonly Button restButton = new Button();
        readonly Button showerButton = new Button();
        readonly Button praiseButton = new Button();
        readonly Button workButton = new Button();
        readonly Button buyButton = new Button();
        readonly Button saveButton = new Button();
        readonly Font titleFont = new Font("Segoe UI", 14, FontStyle.Bold);
        readonly Font uiFont = new Font("Segoe UI", 9, FontStyle.Regular);
        readonly Font smallFont = new Font("Segoe UI", 8, FontStyle.Regular);
        readonly string savePath;
        readonly string androidSaveDir;

        Person selected;
        int money = 650;
        int food = 36;
        int medicine = 2;
        int day = 1;
        int clockMinutes = 8 * 60;
        int simTicks = 0;
        string hover = "";

        public GameForm() : this(true)
        {
        }

        public GameForm(bool startTimer)
        {
            Text = "Virtual Families 2 - Native Rebuild Prototype";
            ClientSize = new Size(1180, 720);
            MinimumSize = new Size(980, 640);
            DoubleBuffered = true;
            BackColor = Color.FromArgb(240, 238, 229);
            savePath = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "vf2-native-save.txt");
            androidSaveDir = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "com.ldw.virtualfamilies2");

            BuildHouse();
            BuildControls();
            LoadOrNew();

            if (startTimer)
            {
                timer.Interval = 33;
                timer.Tick += delegate { Step(); };
                timer.Start();

                MouseClick += OnGameClick;
                MouseMove += OnGameMouseMove;
                FormClosing += delegate { SaveGame(); };
            }
        }

        void BuildHouse()
        {
            rooms.Add(new Room("Kitchen", new Rectangle(35, 92, 330, 210), Color.FromArgb(232, 214, 181), Color.FromArgb(176, 122, 82)));
            rooms.Add(new Room("Living", new Rectangle(365, 92, 370, 210), Color.FromArgb(211, 225, 203), Color.FromArgb(104, 142, 101)));
            rooms.Add(new Room("Bedroom", new Rectangle(735, 92, 360, 210), Color.FromArgb(215, 207, 232), Color.FromArgb(114, 101, 151)));
            rooms.Add(new Room("Bath", new Rectangle(35, 302, 250, 190), Color.FromArgb(206, 228, 233), Color.FromArgb(85, 142, 153)));
            rooms.Add(new Room("Office", new Rectangle(285, 302, 350, 190), Color.FromArgb(230, 220, 199), Color.FromArgb(122, 101, 74)));
            rooms.Add(new Room("Garden", new Rectangle(635, 302, 460, 190), Color.FromArgb(201, 224, 178), Color.FromArgb(91, 133, 72)));

            furniture.Add(new Furniture("Fridge", new Rectangle(70, 130, 55, 95), Color.FromArgb(230, 238, 238), "Kitchen", NeedKind.Fed, 24));
            furniture.Add(new Furniture("Table", new Rectangle(190, 165, 105, 65), Color.FromArgb(142, 94, 55), "Kitchen", NeedKind.Fed, 12));
            furniture.Add(new Furniture("Couch", new Rectangle(430, 210, 170, 55), Color.FromArgb(117, 156, 185), "Living", NeedKind.Happy, 16));
            furniture.Add(new Furniture("TV", new Rectangle(645, 130, 54, 72), Color.FromArgb(43, 47, 54), "Living", NeedKind.Happy, 18));
            furniture.Add(new Furniture("Bed", new Rectangle(790, 170, 200, 85), Color.FromArgb(150, 112, 176), "Bedroom", NeedKind.Energy, 28));
            furniture.Add(new Furniture("Shower", new Rectangle(95, 345, 72, 88), Color.FromArgb(142, 191, 205), "Bath", NeedKind.Clean, 30));
            furniture.Add(new Furniture("Computer", new Rectangle(390, 345, 90, 75), Color.FromArgb(78, 86, 102), "Office", NeedKind.Happy, 6));
            furniture.Add(new Furniture("Workbench", new Rectangle(515, 365, 90, 55), Color.FromArgb(151, 102, 67), "Office", NeedKind.Happy, 8));
            furniture.Add(new Furniture("Flowers", new Rectangle(760, 355, 160, 85), Color.FromArgb(222, 116, 126), "Garden", NeedKind.Happy, 12));
        }

        void BuildControls()
        {
            int x = 35;
            int y = 535;
            MakeButton(feedButton, "Feed", x, y, delegate { CommandNeed(NeedKind.Fed, "Eating", 100); });
            MakeButton(restButton, "Rest", x + 92, y, delegate { CommandNeed(NeedKind.Energy, "Resting", 150); });
            MakeButton(showerButton, "Wash", x + 184, y, delegate { CommandNeed(NeedKind.Clean, "Showering", 110); });
            MakeButton(praiseButton, "Praise", x + 276, y, delegate { CommandNeed(NeedKind.Happy, "Feeling loved", 70); });
            MakeButton(workButton, "Work", x + 368, y, delegate { CommandWork(); });
            MakeButton(buyButton, "Buy Food", x + 460, y, delegate { BuyFood(); });
            MakeButton(saveButton, "Save", x + 570, y, delegate { SaveGame(); AddLog("Game saved."); });
        }

        void MakeButton(Button b, string text, int x, int y, EventHandler click)
        {
            b.Text = text;
            b.Font = uiFont;
            b.SetBounds(x, y, 82, 34);
            b.FlatStyle = FlatStyle.Flat;
            b.BackColor = Color.FromArgb(250, 249, 244);
            b.Click += click;
            Controls.Add(b);
        }

        void LoadOrNew()
        {
            people.Clear();
            if (File.Exists(savePath))
            {
                try
                {
                    string[] lines = File.ReadAllLines(savePath);
                    foreach (string line in lines)
                    {
                        string[] p = line.Split('|');
                        if (p.Length == 2 && p[0] == "money") money = Int32.Parse(p[1], CultureInfo.InvariantCulture);
                        else if (p.Length == 2 && p[0] == "food") food = Int32.Parse(p[1], CultureInfo.InvariantCulture);
                        else if (p.Length == 2 && p[0] == "medicine") medicine = Int32.Parse(p[1], CultureInfo.InvariantCulture);
                        else if (p.Length == 2 && p[0] == "day") day = Int32.Parse(p[1], CultureInfo.InvariantCulture);
                        else if (p.Length == 2 && p[0] == "clock") clockMinutes = Int32.Parse(p[1], CultureInfo.InvariantCulture);
                        else if (p.Length >= 12 && p[0] == "person")
                        {
                            Person person = new Person(p[1], p[2], ParseFloat(p[3]), ParseFloat(p[4]), Color.FromArgb(Int32.Parse(p[11], CultureInfo.InvariantCulture)));
                            person.TargetX = ParseFloat(p[5]);
                            person.TargetY = ParseFloat(p[6]);
                            person.Energy = Int32.Parse(p[7], CultureInfo.InvariantCulture);
                            person.Fed = Int32.Parse(p[8], CultureInfo.InvariantCulture);
                            person.Happy = Int32.Parse(p[9], CultureInfo.InvariantCulture);
                            person.Clean = Int32.Parse(p[10], CultureInfo.InvariantCulture);
                            people.Add(person);
                        }
                    }
                    if (people.Count > 0)
                    {
                        selected = people[0];
                        AddLog("Loaded saved household.");
                        return;
                    }
                }
                catch
                {
                    people.Clear();
                }
            }

            people.Add(new Person("Alex", "Adult", 505, 190, Color.FromArgb(76, 139, 184)));
            people.Add(new Person("Morgan", "Adult", 855, 205, Color.FromArgb(184, 106, 122)));
            people.Add(new Person("Riley", "Child", 720, 385, Color.FromArgb(98, 161, 111)));
            selected = people[0];
            AddLog("New household started.");
        }

        float ParseFloat(string s)
        {
            return Single.Parse(s, CultureInfo.InvariantCulture);
        }

        void Step()
        {
            simTicks++;
            if (simTicks % 20 == 0)
            {
                clockMinutes += 3;
                if (clockMinutes >= 24 * 60)
                {
                    clockMinutes -= 24 * 60;
                    day++;
                    money += 65;
                    AddLog("A new day begins. Paycheck: $65.");
                }

                for (int i = 0; i < people.Count; i++)
                {
                    Person p = people[i];
                    p.Fed = Math.Max(0, p.Fed - 1);
                    if (clockMinutes % 90 == 0) p.Energy = Math.Max(0, p.Energy - 1);
                    if (clockMinutes % 75 == 0) p.Clean = Math.Max(0, p.Clean - 1);
                    if (LowestNeed(p) < 28 && clockMinutes % 60 == 0) p.Happy = Math.Max(0, p.Happy - 2);
                }
            }

            for (int i = 0; i < people.Count; i++)
            {
                Person p = people[i];
                MovePerson(p);
                if (p.ActionTicks > 0)
                {
                    p.ActionTicks--;
                    if (p.ActionTicks == 0)
                    {
                        p.Action = "Wandering";
                    }
                }
                else if (rng.Next(0, 180) == 0)
                {
                    Wander(p);
                }
            }

            Invalidate();
        }

        int LowestNeed(Person p)
        {
            return Math.Min(Math.Min(p.Energy, p.Fed), Math.Min(p.Happy, p.Clean));
        }

        void MovePerson(Person p)
        {
            float dx = p.TargetX - p.X;
            float dy = p.TargetY - p.Y;
            float dist = (float)Math.Sqrt(dx * dx + dy * dy);
            if (dist > 1.5f)
            {
                p.X += dx / dist * 2.0f;
                p.Y += dy / dist * 2.0f;
            }
        }

        void Wander(Person p)
        {
            Room room = rooms[rng.Next(rooms.Count)];
            p.TargetX = room.Area.Left + 38 + rng.Next(Math.Max(20, room.Area.Width - 76));
            p.TargetY = room.Area.Top + 48 + rng.Next(Math.Max(20, room.Area.Height - 76));
        }

        void CommandNeed(NeedKind need, string action, int ticks)
        {
            if (selected == null) return;
            if (need == NeedKind.Fed)
            {
                if (food <= 0)
                {
                    AddLog("The pantry is empty.");
                    return;
                }
                food--;
            }
            Furniture target = BestFurniture(need);
            if (target != null)
            {
                selected.TargetX = target.Area.Left + target.Area.Width / 2;
                selected.TargetY = target.Area.Top + target.Area.Height + 24;
                selected.SetNeed(need, selected.Need(need) + target.Boost);
            }
            else
            {
                selected.SetNeed(need, selected.Need(need) + 12);
            }
            selected.Action = action;
            selected.ActionTicks = ticks;
            AddLog(selected.Name + ": " + action.ToLowerInvariant() + ".");
        }

        Furniture BestFurniture(NeedKind need)
        {
            Furniture best = null;
            for (int i = 0; i < furniture.Count; i++)
            {
                if (furniture[i].Need == need && (best == null || furniture[i].Boost > best.Boost))
                    best = furniture[i];
            }
            return best;
        }

        void CommandWork()
        {
            if (selected == null) return;
            selected.TargetX = 435;
            selected.TargetY = 445;
            selected.Action = "Working";
            selected.ActionTicks = 165;
            selected.Energy = Math.Max(0, selected.Energy - 10);
            selected.Happy = Math.Max(0, selected.Happy - 3);
            int earned = 28 + rng.Next(20);
            money += earned;
            AddLog(selected.Name + " earned $" + earned + ".");
        }

        void BuyFood()
        {
            if (money < 45)
            {
                AddLog("Not enough money for groceries.");
                return;
            }
            money -= 45;
            food += 12;
            AddLog("Bought groceries. Food +" + 12 + ".");
        }

        void AddLog(string entry)
        {
            log.Insert(0, ClockText() + "  " + entry);
            while (log.Count > 7) log.RemoveAt(log.Count - 1);
        }

        string ClockText()
        {
            int h = clockMinutes / 60;
            int m = clockMinutes % 60;
            string suffix = h >= 12 ? "PM" : "AM";
            int hh = h % 12;
            if (hh == 0) hh = 12;
            return "Day " + day + " " + hh.ToString(CultureInfo.InvariantCulture) + ":" + m.ToString("00", CultureInfo.InvariantCulture) + " " + suffix;
        }

        void SaveGame()
        {
            StringBuilder sb = new StringBuilder();
            sb.AppendLine("money|" + money.ToString(CultureInfo.InvariantCulture));
            sb.AppendLine("food|" + food.ToString(CultureInfo.InvariantCulture));
            sb.AppendLine("medicine|" + medicine.ToString(CultureInfo.InvariantCulture));
            sb.AppendLine("day|" + day.ToString(CultureInfo.InvariantCulture));
            sb.AppendLine("clock|" + clockMinutes.ToString(CultureInfo.InvariantCulture));
            for (int i = 0; i < people.Count; i++)
            {
                Person p = people[i];
                sb.Append("person|").Append(p.Name).Append("|").Append(p.Role).Append("|")
                    .Append(p.X.ToString(CultureInfo.InvariantCulture)).Append("|")
                    .Append(p.Y.ToString(CultureInfo.InvariantCulture)).Append("|")
                    .Append(p.TargetX.ToString(CultureInfo.InvariantCulture)).Append("|")
                    .Append(p.TargetY.ToString(CultureInfo.InvariantCulture)).Append("|")
                    .Append(p.Energy.ToString(CultureInfo.InvariantCulture)).Append("|")
                    .Append(p.Fed.ToString(CultureInfo.InvariantCulture)).Append("|")
                    .Append(p.Happy.ToString(CultureInfo.InvariantCulture)).Append("|")
                    .Append(p.Clean.ToString(CultureInfo.InvariantCulture)).Append("|")
                    .Append(p.Shirt.ToArgb().ToString(CultureInfo.InvariantCulture)).AppendLine();
            }
            File.WriteAllText(savePath, sb.ToString());
            WriteAndroidStyleSave();
        }

        public void SaveGameForCommandLine()
        {
            SaveGame();
        }

        void WriteAndroidStyleSave()
        {
            Directory.CreateDirectory(androidSaveDir);
            File.WriteAllText(Path.Combine(androidSaveDir, "ldwlog.txt"), "");
            File.WriteAllText(Path.Combine(androidSaveDir, "wc.dat"),
                "{\"vf2\":{\"interstitials\":{\"exclude_payers\":0,\"session\":20,\"video\":600,\"max_per_day\":3,\"min\":180,\"tutorial\":900,\"first_days\":3,\"first\":3600}},\"session_id\":\"native-prototype-session\",\"id\":\"native-prototype\"}");

            byte[] slotIndex = BuildSlotIndexLdw();
            File.WriteAllBytes(Path.Combine(androidSaveDir, "virtual families 20.ldw"), slotIndex);

            byte[] gameSave = BuildGameStateLdw(false);
            File.WriteAllBytes(Path.Combine(androidSaveDir, "virtual families 21.ldw"), gameSave);

            byte[] backupSave = BuildGameStateLdw(true);
            File.WriteAllBytes(Path.Combine(androidSaveDir, "virtual families 221.ldw"), backupSave);
        }

        byte[] BuildSlotIndexLdw()
        {
            byte[] data = NewLdwFile(220);
            PutInt(data, 0x0c, 1);
            PutInt(data, 0x14, 1);
            PutInt(data, 0x1c, 1539);
            PutInt(data, 0x20, Math.Max(1, money * 137 + day));

            string[] labels = new string[] { HouseholdLabel(), "NEW PLAYER", "NEW PLAYER", "NEW PLAYER", "NEW PLAYER" };
            int[] offsets = new int[] { 0x24, 0x38, 0x4c, 0x60, 0x78 };
            for (int i = 0; i < labels.Length; i++)
                PutFixedString(data, offsets[i], labels[i], 18);

            PutInt(data, 0x8c, 256);
            PutInt(data, 0x94, 999);
            int unix = CurrentUnixTime();
            PutInt(data, 0x9c, unix);
            PutInt(data, 0xa0, unix);
            PutInt(data, 0xa4, 1);
            PutInt(data, 0xac, money);
            PutInt(data, 0xb0, food);
            PutInt(data, 0xb4, day);
            PutInt(data, 0xbc, unix);
            return data;
        }

        byte[] BuildGameStateLdw(bool backup)
        {
            byte[] data = NewLdwFile(154400);

            PutInt(data, 0x4c, people.Count);
            PutInt(data, 0x70, 1);
            PutInt(data, 0xa0, 1);
            PutInt(data, 0xc0, 1);
            PutInt(data, 0xf0, 1);
            PutInt(data, 0x100, money);
            PutInt(data, 0x104, food);
            PutInt(data, 0x108, medicine);
            PutInt(data, 0x10c, day);
            PutInt(data, 0x110, clockMinutes);

            WriteNameCatalogue(data);
            WriteWorldState(data, backup);
            WritePersonSlots(data, backup);
            WriteTailState(data, backup);
            return data;
        }

        void WriteNameCatalogue(byte[] data)
        {
            string[] names = new string[]
            {
                "Cocoa", "Bingone", "Crisor", "Margette", "Kikolo", "Brunu", "Marella",
                "Apollo", "Aspen", "Taffy", "Sophina", "Smiley", "Vector", "Opus",
                "Viva", "Caria", "Webby", "Fria", "Logory", "Pennesse", "Brina"
            };
            string[] traits = new string[]
            {
                " jokes, art", " loose socks", " chicken", " toys, bushes", " burgers",
                " eating", " shopping", " playing", " babies", " thunder", " work",
                " music", " vegetables, lightning", " medicine", " sweets", " BBQ, grass"
            };

            int offset = 0x184c;
            for (int i = 0; i < names.Length && offset + 0x5c < 0x5500; i++)
            {
                PutFixedString(data, offset, names[i], 24);
                PutInt(data, offset + 0x1c, i % 2);
                PutInt(data, offset + 0x20, 20 + i);
                PutInt(data, offset + 0x24, 10 + i);
                if (i < traits.Length)
                    PutFixedString(data, offset + 0x34, traits[i], 36);
                offset += 0xdc;
            }
        }

        void WriteWorldState(byte[] data, bool backup)
        {
            int objectBase = 0xe000;
            int stride = 0x40;
            int objectCount = Math.Min(250, furniture.Count * 24);
            for (int i = 0; i < objectCount; i++)
            {
                Furniture f = furniture[i % furniture.Count];
                int at = objectBase + i * stride;
                PutInt(data, at + 0x00, i + 1);
                PutInt(data, at + 0x04, f.Area.X);
                PutInt(data, at + 0x08, f.Area.Y);
                PutInt(data, at + 0x0c, f.Area.Width);
                PutInt(data, at + 0x10, f.Area.Height);
                PutInt(data, at + 0x24, (int)f.Need);
                PutInt(data, at + 0x28, (backup ? clockMinutes + 7 : clockMinutes) + i * 17);
                PutInt(data, at + 0x2c, f.Boost);
                PutInt(data, at + 0x30, money + food + i);
            }
        }

        void WritePersonSlots(byte[] data, bool backup)
        {
            string[] fallback = new string[]
            {
                "Magica", "Franella", "Trishie", "Smiley", "Katila", "Sophella",
                "Pennette", "Petta", "Marcor", "Gepu", "Trishina", "Uffa"
            };
            int start = 0x172b0;
            int stride = 0x7bc;
            for (int slot = 0; slot < 12; slot++)
            {
                int at = start + slot * stride;
                Person p = slot < people.Count ? people[slot] : null;
                string name = p == null ? fallback[slot] : p.Name;
                int active = p == null ? 0 : 1;
                int role = p == null ? 1 : (p.Role == "Child" ? 0 : 1);
                int seed = StableHash(name);

                PutInt(data, at + 0x00, 120 + slot * 17 + active);
                PutInt(data, at + 0x04, active);
                PutInt(data, at + 0x08, 80 + slot * 7);
                PutInt(data, at + 0x0c, role);
                PutFixedString(data, at + 0x10, name, 32);
                PutInt(data, at + 0x2c, slot < people.Count ? 11 + slot : slot);
                PutInt(data, at + 0x30, slot < people.Count ? 18 + slot : 0);

                if (p != null)
                {
                    PutInt(data, at + 0xa0, (int)p.X);
                    PutInt(data, at + 0xa4, (int)p.Y);
                    PutInt(data, at + 0xa8, (int)p.TargetX);
                    PutInt(data, at + 0xac, (int)p.TargetY);
                    PutInt(data, at + 0xd0, p.Energy);
                    PutInt(data, at + 0xd4, p.Fed);
                    PutInt(data, at + 0xd8, p.Happy);
                    PutInt(data, at + 0xdc, p.Clean);
                    PutInt(data, at + 0xe0, p.ActionTicks + (backup ? 3 : 0));
                    PutFixedString(data, at + 0xf4, p.Action, 48);
                    PutInt(data, at + 0x130, p.Shirt.ToArgb());
                    PutInt(data, at + 0x140, LowestNeed(p));
                }

                PutInt(data, at + 0x2a0, seed);
                PutInt(data, at + 0x2a4, money + slot);
                PutInt(data, at + 0x2a8, food + slot);
                PutInt(data, at + 0x2ac, day);
                PutInt(data, at + 0x2b0, clockMinutes + (backup ? 1 : 0));
            }
        }

        void WriteTailState(byte[] data, bool backup)
        {
            int start = 0x1cf80;
            int state = money * 31 + food * 17 + medicine * 13 + day * 7 + clockMinutes;
            if (backup) state += 101;
            for (int at = start; at + 4 <= data.Length; at += 4)
            {
                state = unchecked(state * 1103515245 + 12345);
                PutInt(data, at, state);
            }
        }

        byte[] NewLdwFile(int size)
        {
            byte[] data = new byte[size];
            data[0] = (byte)'l';
            data[1] = (byte)'d';
            data[2] = (byte)'w';
            data[3] = (byte)'g';
            data[4] = 0x00;
            data[5] = 0x6f;
            data[6] = 0x71;
            data[7] = 0x5e;
            PutInt(data, 0x08, size - 12);
            return data;
        }

        void PutInt(byte[] data, int offset, int value)
        {
            if (offset < 0 || offset + 4 > data.Length) return;
            data[offset] = (byte)(value & 0xff);
            data[offset + 1] = (byte)((value >> 8) & 0xff);
            data[offset + 2] = (byte)((value >> 16) & 0xff);
            data[offset + 3] = (byte)((value >> 24) & 0xff);
        }

        void PutFixedString(byte[] data, int offset, string value, int length)
        {
            if (offset < 0 || offset >= data.Length || length <= 0) return;
            byte[] raw = Encoding.ASCII.GetBytes(value);
            int count = Math.Min(Math.Min(raw.Length, length - 1), data.Length - offset);
            Array.Copy(raw, 0, data, offset, count);
        }

        int CurrentUnixTime()
        {
            TimeSpan span = DateTime.UtcNow - new DateTime(1970, 1, 1);
            return (int)span.TotalSeconds;
        }

        int StableHash(string text)
        {
            unchecked
            {
                int hash = 5381;
                for (int i = 0; i < text.Length; i++)
                    hash = ((hash << 5) + hash) ^ text[i];
                return hash;
            }
        }

        string HouseholdLabel()
        {
            if (people.Count == 0) return "NEW PLAYER";
            string label = people[0].Name + " HOUSE";
            return label.Length > 18 ? label.Substring(0, 18) : label;
        }

        void OnGameClick(object sender, MouseEventArgs e)
        {
            for (int i = people.Count - 1; i >= 0; i--)
            {
                Person p = people[i];
                Rectangle r = PersonBounds(p);
                if (r.Contains(e.Location))
                {
                    selected = p;
                    AddLog("Selected " + p.Name + ".");
                    return;
                }
            }

            for (int i = 0; i < furniture.Count; i++)
            {
                Furniture f = furniture[i];
                if (f.Area.Contains(e.Location))
                {
                    if (selected != null)
                    {
                        selected.TargetX = f.Area.Left + f.Area.Width / 2;
                        selected.TargetY = f.Area.Top + f.Area.Height + 25;
                        selected.SetNeed(f.Need, selected.Need(f.Need) + f.Boost);
                        selected.Action = "Using " + f.Name;
                        selected.ActionTicks = 120;
                        AddLog(selected.Name + " is using " + f.Name + ".");
                    }
                    return;
                }
            }

            if (e.Y < 505 && selected != null)
            {
                selected.TargetX = e.X;
                selected.TargetY = e.Y;
                selected.Action = "Walking";
                selected.ActionTicks = 50;
            }
        }

        void OnGameMouseMove(object sender, MouseEventArgs e)
        {
            hover = "";
            for (int i = 0; i < furniture.Count; i++)
            {
                if (furniture[i].Area.Contains(e.Location))
                {
                    hover = furniture[i].Name + " - boosts " + furniture[i].Need.ToString().ToLowerInvariant();
                    break;
                }
            }
        }

        Rectangle PersonBounds(Person p)
        {
            int h = p.Role == "Child" ? 45 : 58;
            int w = p.Role == "Child" ? 26 : 32;
            return new Rectangle((int)p.X - w / 2, (int)p.Y - h, w, h);
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            Graphics g = e.Graphics;
            g.SmoothingMode = System.Drawing.Drawing2D.SmoothingMode.AntiAlias;
            DrawHeader(g);
            DrawHouse(g);
            DrawPeople(g);
            DrawPanel(g);
        }

        void DrawHeader(Graphics g)
        {
            using (Brush b = new SolidBrush(Color.FromArgb(64, 58, 50)))
                g.DrawString("Virtual Families 2 - Native Rebuild Prototype", titleFont, b, 35, 22);
            using (Brush b = new SolidBrush(Color.FromArgb(83, 79, 70)))
                g.DrawString(ClockText() + "    $" + money + "    Food " + food + "    Medicine " + medicine, uiFont, b, 38, 55);
        }

        void DrawHouse(Graphics g)
        {
            using (Pen wallPen = new Pen(Color.FromArgb(117, 101, 82), 4))
            {
                for (int i = 0; i < rooms.Count; i++)
                {
                    Room r = rooms[i];
                    using (Brush fill = new SolidBrush(r.Fill))
                        g.FillRectangle(fill, r.Area);
                    using (Pen accent = new Pen(r.Accent, 2))
                        g.DrawRectangle(accent, r.Area);
                    using (Brush text = new SolidBrush(Color.FromArgb(70, 63, 54)))
                        g.DrawString(r.Name, uiFont, text, r.Area.Left + 12, r.Area.Top + 10);
                }
                g.DrawRectangle(wallPen, new Rectangle(35, 92, 1060, 400));
            }

            for (int i = 0; i < furniture.Count; i++)
                DrawFurniture(g, furniture[i]);
        }

        void DrawFurniture(Graphics g, Furniture f)
        {
            using (Brush shadow = new SolidBrush(Color.FromArgb(70, 0, 0, 0)))
                g.FillEllipse(shadow, f.Area.Left + 4, f.Area.Bottom - 6, f.Area.Width - 8, 16);
            using (Brush fill = new SolidBrush(f.Fill))
                g.FillRectangle(fill, f.Area);
            using (Pen pen = new Pen(Color.FromArgb(70, 63, 54), 2))
                g.DrawRectangle(pen, f.Area);
            using (Brush text = new SolidBrush(Color.FromArgb(54, 48, 42)))
                g.DrawString(f.Name, smallFont, text, f.Area.Left + 4, f.Area.Top + 4);
        }

        void DrawPeople(Graphics g)
        {
            for (int i = 0; i < people.Count; i++)
            {
                Person p = people[i];
                bool isSelected = p == selected;
                Rectangle body = PersonBounds(p);
                if (isSelected)
                {
                    using (Pen ring = new Pen(Color.FromArgb(235, 179, 68), 3))
                        g.DrawEllipse(ring, (int)p.X - 25, (int)p.Y - 13, 50, 18);
                }
                using (Brush skin = new SolidBrush(Color.FromArgb(228, 178, 132)))
                    g.FillEllipse(skin, body.Left + body.Width / 2 - 10, body.Top, 20, 20);
                using (Brush shirt = new SolidBrush(p.Shirt))
                    g.FillRoundedRectangle(shirt, new Rectangle(body.Left, body.Top + 18, body.Width, body.Height - 20), 8);
                using (Pen outline = new Pen(Color.FromArgb(63, 55, 48), 2))
                    g.DrawRoundedRectangle(outline, new Rectangle(body.Left, body.Top + 18, body.Width, body.Height - 20), 8);
                using (Brush text = new SolidBrush(Color.FromArgb(51, 45, 39)))
                    g.DrawString(p.Name, smallFont, text, p.X - 24, p.Y + 5);
            }
        }

        void DrawPanel(Graphics g)
        {
            Rectangle side = new Rectangle(720, 525, 375, 155);
            using (Brush panel = new SolidBrush(Color.FromArgb(250, 249, 244)))
                g.FillRectangle(panel, side);
            using (Pen pen = new Pen(Color.FromArgb(181, 171, 150)))
                g.DrawRectangle(pen, side);

            if (selected != null)
            {
                using (Brush text = new SolidBrush(Color.FromArgb(54, 48, 42)))
                {
                    g.DrawString(selected.Name + " (" + selected.Role + ")", titleFont, text, side.Left + 16, side.Top + 12);
                    g.DrawString(selected.Action, uiFont, text, side.Left + 18, side.Top + 42);
                }
                DrawNeed(g, "Energy", selected.Energy, side.Left + 18, side.Top + 72, Color.FromArgb(109, 143, 196));
                DrawNeed(g, "Fed", selected.Fed, side.Left + 18, side.Top + 92, Color.FromArgb(116, 167, 102));
                DrawNeed(g, "Happy", selected.Happy, side.Left + 190, side.Top + 72, Color.FromArgb(210, 154, 68));
                DrawNeed(g, "Clean", selected.Clean, side.Left + 190, side.Top + 92, Color.FromArgb(81, 164, 181));
            }

            Rectangle feed = new Rectangle(35, 585, 660, 95);
            using (Brush panel = new SolidBrush(Color.FromArgb(250, 249, 244)))
                g.FillRectangle(panel, feed);
            using (Pen pen = new Pen(Color.FromArgb(181, 171, 150)))
                g.DrawRectangle(pen, feed);
            using (Brush text = new SolidBrush(Color.FromArgb(64, 58, 50)))
            {
                g.DrawString("Household log", uiFont, text, feed.Left + 12, feed.Top + 10);
                for (int i = 0; i < log.Count; i++)
                    g.DrawString(log[i], smallFont, text, feed.Left + 12, feed.Top + 31 + i * 13);
                if (hover.Length > 0)
                    g.DrawString(hover, smallFont, text, 720, 496);
            }
        }

        void DrawNeed(Graphics g, string label, int value, int x, int y, Color color)
        {
            using (Brush text = new SolidBrush(Color.FromArgb(64, 58, 50)))
                g.DrawString(label, smallFont, text, x, y - 2);
            Rectangle bar = new Rectangle(x + 55, y, 95, 10);
            using (Brush bg = new SolidBrush(Color.FromArgb(224, 219, 205)))
                g.FillRectangle(bg, bar);
            using (Brush fg = new SolidBrush(color))
                g.FillRectangle(fg, new Rectangle(bar.Left, bar.Top, value * bar.Width / 100, bar.Height));
            using (Pen pen = new Pen(Color.FromArgb(164, 154, 132)))
                g.DrawRectangle(pen, bar);
        }
    }

    static class GraphicsExtensions
    {
        public static void FillRoundedRectangle(this Graphics g, Brush brush, Rectangle bounds, int radius)
        {
            using (System.Drawing.Drawing2D.GraphicsPath path = RoundedPath(bounds, radius))
                g.FillPath(brush, path);
        }

        public static void DrawRoundedRectangle(this Graphics g, Pen pen, Rectangle bounds, int radius)
        {
            using (System.Drawing.Drawing2D.GraphicsPath path = RoundedPath(bounds, radius))
                g.DrawPath(pen, path);
        }

        static System.Drawing.Drawing2D.GraphicsPath RoundedPath(Rectangle bounds, int radius)
        {
            int d = radius * 2;
            System.Drawing.Drawing2D.GraphicsPath path = new System.Drawing.Drawing2D.GraphicsPath();
            path.AddArc(bounds.Left, bounds.Top, d, d, 180, 90);
            path.AddArc(bounds.Right - d, bounds.Top, d, d, 270, 90);
            path.AddArc(bounds.Right - d, bounds.Bottom - d, d, d, 0, 90);
            path.AddArc(bounds.Left, bounds.Bottom - d, d, d, 90, 90);
            path.CloseFigure();
            return path;
        }
    }

    static class AndroidStyleSampleSave
    {
        public static void Write(string baseDir)
        {
            string dir = Path.Combine(baseDir, "com.ldw.virtualfamilies2");
            Directory.CreateDirectory(dir);
            File.WriteAllText(Path.Combine(dir, "ldwlog.txt"), "");
            File.WriteAllText(Path.Combine(dir, "wc.dat"),
                "{\"vf2\":{\"interstitials\":{\"exclude_payers\":0,\"session\":20,\"video\":600,\"max_per_day\":3,\"min\":180,\"tutorial\":900,\"first_days\":3,\"first\":3600}},\"session_id\":\"native-prototype-session\",\"id\":\"native-prototype\"}");
            File.WriteAllBytes(Path.Combine(dir, "virtual families 20.ldw"), BuildIndex());
            File.WriteAllBytes(Path.Combine(dir, "virtual families 21.ldw"), BuildLarge(false));
            File.WriteAllBytes(Path.Combine(dir, "virtual families 221.ldw"), BuildLarge(true));
        }

        static byte[] BuildIndex()
        {
            byte[] data = NewLdwFile(220);
            PutInt(data, 0x0c, 1);
            PutInt(data, 0x14, 1);
            PutInt(data, 0x1c, 1539);
            PutInt(data, 0x20, 100045);
            PutFixedString(data, 0x24, "ALEX HOUSE", 18);
            PutFixedString(data, 0x38, "NEW PLAYER", 18);
            PutFixedString(data, 0x4c, "NEW PLAYER", 18);
            PutFixedString(data, 0x60, "NEW PLAYER", 18);
            PutFixedString(data, 0x78, "NEW PLAYER", 18);
            PutInt(data, 0x8c, 256);
            PutInt(data, 0x94, 999);
            int now = CurrentUnixTime();
            PutInt(data, 0x9c, now);
            PutInt(data, 0xa0, now);
            PutInt(data, 0xa4, 1);
            PutInt(data, 0xac, 650);
            PutInt(data, 0xb0, 36);
            PutInt(data, 0xb4, 1);
            PutInt(data, 0xbc, now);
            return data;
        }

        static byte[] BuildLarge(bool backup)
        {
            byte[] data = NewLdwFile(154400);
            PutInt(data, 0x4c, 3);
            PutInt(data, 0x70, 1);
            PutInt(data, 0xa0, 1);
            PutInt(data, 0xc0, 1);
            PutInt(data, 0xf0, 1);
            PutInt(data, 0x100, 650);
            PutInt(data, 0x104, 36);
            PutInt(data, 0x108, 2);
            PutInt(data, 0x10c, 1);
            PutInt(data, 0x110, 480);

            WriteCatalogue(data);
            WriteObjects(data, backup);
            WritePeople(data, backup);
            WriteTail(data, backup);
            return data;
        }

        static void WriteCatalogue(byte[] data)
        {
            string[] names = new string[] { "Cocoa", "Bingone", "Crisor", "Margette", "Kikolo", "Brunu", "Marella", "Apollo", "Aspen", "Taffy", "Sophina", "Smiley" };
            string[] traits = new string[] { " jokes, art", " loose socks", " chicken", " toys, bushes", " burgers", " eating", " shopping", " playing", " babies", " thunder", " work", " music" };
            int offset = 0x184c;
            for (int i = 0; i < names.Length; i++)
            {
                PutFixedString(data, offset, names[i], 24);
                PutInt(data, offset + 0x1c, i % 2);
                PutInt(data, offset + 0x20, 20 + i);
                PutInt(data, offset + 0x24, 10 + i);
                PutFixedString(data, offset + 0x34, traits[i], 36);
                offset += 0xdc;
            }
        }

        static void WriteObjects(byte[] data, bool backup)
        {
            int objectBase = 0xe000;
            int stride = 0x40;
            for (int i = 0; i < 216; i++)
            {
                int at = objectBase + i * stride;
                PutInt(data, at + 0x00, i + 1);
                PutInt(data, at + 0x04, 40 + (i % 12) * 82);
                PutInt(data, at + 0x08, 100 + (i % 5) * 72);
                PutInt(data, at + 0x0c, 48 + (i % 4) * 12);
                PutInt(data, at + 0x10, 38 + (i % 3) * 16);
                PutInt(data, at + 0x24, i % 4);
                PutInt(data, at + 0x28, 480 + i * 17 + (backup ? 7 : 0));
                PutInt(data, at + 0x2c, 12 + i % 30);
                PutInt(data, at + 0x30, 686 + i);
            }
        }

        static void WritePeople(byte[] data, bool backup)
        {
            string[] names = new string[] { "Alex", "Morgan", "Riley", "Smiley", "Katila", "Sophella", "Pennette", "Petta", "Marcor", "Gepu", "Trishina", "Uffa" };
            int[,] needs = new int[,] { { 76, 74, 70, 78 }, { 76, 74, 70, 78 }, { 76, 74, 70, 78 } };
            int start = 0x172b0;
            int stride = 0x7bc;
            for (int slot = 0; slot < 12; slot++)
            {
                int at = start + slot * stride;
                int active = slot < 3 ? 1 : 0;
                PutInt(data, at + 0x00, 120 + slot * 17 + active);
                PutInt(data, at + 0x04, active);
                PutInt(data, at + 0x08, 80 + slot * 7);
                PutInt(data, at + 0x0c, slot == 2 ? 0 : 1);
                PutFixedString(data, at + 0x10, names[slot], 32);
                PutInt(data, at + 0x2c, slot < 3 ? 11 + slot : slot);
                PutInt(data, at + 0x30, slot < 3 ? 18 + slot : 0);
                if (slot < 3)
                {
                    PutInt(data, at + 0xa0, 505 + slot * 120);
                    PutInt(data, at + 0xa4, 190 + slot * 70);
                    PutInt(data, at + 0xa8, 505 + slot * 120);
                    PutInt(data, at + 0xac, 190 + slot * 70);
                    PutInt(data, at + 0xd0, needs[slot, 0]);
                    PutInt(data, at + 0xd4, needs[slot, 1]);
                    PutInt(data, at + 0xd8, needs[slot, 2]);
                    PutInt(data, at + 0xdc, needs[slot, 3]);
                    PutInt(data, at + 0xe0, backup ? 3 : 0);
                    PutFixedString(data, at + 0xf4, "Wandering", 48);
                }
                PutInt(data, at + 0x2a0, StableHash(names[slot]));
                PutInt(data, at + 0x2a4, 650 + slot);
                PutInt(data, at + 0x2a8, 36 + slot);
                PutInt(data, at + 0x2ac, 1);
                PutInt(data, at + 0x2b0, 480 + (backup ? 1 : 0));
            }
        }

        static void WriteTail(byte[] data, bool backup)
        {
            int state = backup ? 424343 : 424242;
            for (int at = 0x1cf80; at + 4 <= data.Length; at += 4)
            {
                state = unchecked(state * 1103515245 + 12345);
                PutInt(data, at, state);
            }
        }

        static byte[] NewLdwFile(int size)
        {
            byte[] data = new byte[size];
            data[0] = (byte)'l';
            data[1] = (byte)'d';
            data[2] = (byte)'w';
            data[3] = (byte)'g';
            data[4] = 0x00;
            data[5] = 0x6f;
            data[6] = 0x71;
            data[7] = 0x5e;
            PutInt(data, 0x08, size - 12);
            return data;
        }

        static void PutInt(byte[] data, int offset, int value)
        {
            data[offset] = (byte)(value & 0xff);
            data[offset + 1] = (byte)((value >> 8) & 0xff);
            data[offset + 2] = (byte)((value >> 16) & 0xff);
            data[offset + 3] = (byte)((value >> 24) & 0xff);
        }

        static void PutFixedString(byte[] data, int offset, string value, int length)
        {
            byte[] raw = Encoding.ASCII.GetBytes(value);
            int count = Math.Min(raw.Length, length - 1);
            Array.Copy(raw, 0, data, offset, count);
        }

        static int CurrentUnixTime()
        {
            TimeSpan span = DateTime.UtcNow - new DateTime(1970, 1, 1);
            return (int)span.TotalSeconds;
        }

        static int StableHash(string text)
        {
            unchecked
            {
                int hash = 5381;
                for (int i = 0; i < text.Length; i++)
                    hash = ((hash << 5) + hash) ^ text[i];
                return hash;
            }
        }
    }
}
